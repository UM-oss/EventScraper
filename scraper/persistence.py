"""
Persistent storage logika za dogodke.

Glavni del Phase 1 refactorja: NAMESTO BRISANJA in re-INSERT delamo
UPSERT (update existing OR insert new) in mark-stale za dogodke ki jih
scraper ni več našel.

To pomeni:
- Editorial statusi (approved/skipped) v event_media tabeli ostanejo nedotaknjeni.
- Zgodovina sprememb (event_edits) ostane.
- Dogodki ki izginejo iz vira se označijo z is_active=False, NE pobrišejo.
- Pri dnevnem scrape-u dobimo realni "delta": koliko novih, koliko posodobljenih,
  koliko ne-najdenih (potencialno odpovedanih).
"""

import logging
from dataclasses import dataclass
from datetime import datetime, date
from typing import Optional

from database.models import Event, EventEdit, DedupDecision, ScrapeLog
from scraper.dedup import (
    DedupConfig, check_dedup, find_existing_event, compute_dedup_hash, normalize_text,
)
from scraper.categorizer import categorize_event

logger = logging.getLogger(__name__)


# Polja, ki jih scraper sme prepisovati z novejšimi podatki iz vira.
# (Ne prepisuje uredniško urejenih polj — zato beležimo description_source.)
SCRAPER_OVERWRITABLE_FIELDS = {
    "title", "description", "date_start", "date_end",
    "time_start", "time_end", "location", "address",
    "price", "organizer", "categories", "district",
    "image_url", "source_url", "detail_url", "ticket_url",
    "categories",
}

# Polja, ki jih NE prepišemo, če je urednik že ročno spremenil
# (ima description_source != 'scraped' za opis in image_source za sliko).
USER_PROTECTED_FIELDS = {"description", "image_url"}


@dataclass
class UpsertStats:
    new: int = 0
    updated: int = 0
    duplicate: int = 0
    skipped: int = 0  # razstave, manjkajoča polja itd.
    new_ids: list = None
    updated_ids: list = None

    def __post_init__(self):
        if self.new_ids is None:
            self.new_ids = []
        if self.updated_ids is None:
            self.updated_ids = []


def _is_too_long_exhibition(event):
    """Razstave > 2 dni, ki niso 'odprtja', preskočimo."""
    if event.event_type != "razstava":
        return False
    if not (event.date_start and event.date_end):
        return False
    duration = (event.date_end - event.date_start).days
    if duration <= 2:
        return False
    title_lower = (event.title or "").lower()
    is_opening = any(w in title_lower for w in ["odprtje", "otvoritev", "vernisaž", "opening"])
    return not is_opening


def _has_at_least_one_key_field(event):
    """Vsaj eno od (prizorišče, tip).
    (Organizator in vstopnina nista več prikazana v UI, zato nista obvezna.)"""
    return bool(event.location or event.address or event.event_type)


def _apply_event_data_to_model(event: Event, data: dict, is_new: bool):
    """
    Posodobi polja Event modela iz scrape data dict-a.

    Vrne (changed: bool, edits: list).
    `changed=True` pomeni vsaj eno polje se je spremenilo (sproži version++).
    `edits` so EventEdit zapisi (le za "pomembna" polja, da ni preveč šuma).
    """
    edits = []
    changed = False
    important_fields = {"title", "description", "date_start", "time_start",
                        "location", "organizer", "image_url"}
    for field in SCRAPER_OVERWRITABLE_FIELDS:
        new_val = data.get(field)
        if new_val is None or new_val == "":
            continue

        if not is_new and field in USER_PROTECTED_FIELDS:
            current_source = (
                event.description_source if field == "description"
                else event.image_source
            )
            if current_source in ("manual", "ai-generated"):
                continue

        old_val = getattr(event, field, None)
        if old_val == new_val:
            continue

        setattr(event, field, new_val)
        changed = True

        if not is_new and field in important_fields:
            edits.append(EventEdit(
                field_name=field,
                old_value=str(old_val) if old_val is not None else None,
                new_value=str(new_val),
                source="scraper",
            ))
    return changed, edits


def upsert_event(
    db_session,
    event_data: dict,
    source_id: str,
    region: Optional[str],
    config: Optional[DedupConfig] = None,
    log_dedup_decision: bool = True,
) -> tuple[str, Optional[Event]]:
    """
    Glavna upsert funkcija.

    Vrne:
      ("new", event)        — nov dogodek shranjen
      ("updated", event)    — obstoječi dogodek posodobljen (po source_event_id ujemanju)
      ("duplicate", None)   — fuzzy duplikat z drugim dogodkom — preskočen
      ("skipped", None)     — manjka ključno polje, razstava, pretekli, itd.
    """
    title = event_data.get("title", "").strip()
    date_start = event_data.get("date_start")
    if not title:
        return "skipped", None

    cutoff_date = date.today()
    if date_start and date_start < cutoff_date:
        return "skipped", None

    # --- 1. Direktni hit po (source_id, source_event_id) ---
    source_event_id = event_data.get("source_event_id")
    existing = find_existing_event(db_session, source_id, source_event_id)

    if existing is not None:
        # Posodobi obstoječi dogodek
        existing.last_seen_at = datetime.utcnow()
        existing.last_scraped_at = datetime.utcnow()
        existing.is_active = True

        changed, edits = _apply_event_data_to_model(existing, event_data, is_new=False)
        # NE re-kategoriziraj obstoječih dogodkov — uporabnikova zahteva.
        # Kategorizacija velja samo za nove dogodke (spodaj).

        if _is_too_long_exhibition(existing) or not _has_at_least_one_key_field(existing):
            existing.is_active = False
            db_session.flush()
            return "skipped", None

        existing.completeness = existing.calculate_completeness()
        if changed:
            existing.version += 1
        for e in edits:
            e.event_id = existing.id
            db_session.add(e)
        db_session.flush()
        return "updated", existing

    # --- 2. Fuzzy dedup proti vsem dogodkom istega datuma ---
    dedup_result = check_dedup(
        db_session, title, date_start,
        time_start=event_data.get("time_start"),
        location=event_data.get("location"),
        config=config,
    )

    if log_dedup_decision and dedup_result.decision != "new":
        try:
            db_session.add(DedupDecision(
                incoming_title=title[:500],
                incoming_source_id=source_id,
                incoming_date=date_start,
                incoming_time=(event_data.get("time_start") or "")[:10] or None,
                incoming_location=(event_data.get("location") or "")[:500] or None,
                matched_event_id=dedup_result.matched_event_id,
                matched_title=(dedup_result.matched_title or "")[:500] or None,
                decision=dedup_result.decision,
                reason=dedup_result.reason,
                score=dedup_result.score,
                threshold=dedup_result.threshold,
            ))
        except Exception as e:
            logger.debug(f"Dedup decision log failed: {e}")

    if dedup_result.decision == "duplicate":
        # Posodobi last_seen_at na obstoječem dogodku (vir ga je še najdel)
        if dedup_result.matched_event_id:
            matched = db_session.query(Event).get(dedup_result.matched_event_id)
            if matched:
                matched.last_seen_at = datetime.utcnow()
                matched.is_active = True
        return "duplicate", None

    # --- 3. Nov dogodek ---
    dedup_hash = compute_dedup_hash(title, date_start, event_data.get("location"))
    event = Event(
        title=title,
        description=event_data.get("description"),
        date_start=date_start,
        date_end=event_data.get("date_end"),
        time_start=event_data.get("time_start"),
        time_end=event_data.get("time_end"),
        location=event_data.get("location"),
        address=event_data.get("address"),
        price=event_data.get("price"),
        organizer=event_data.get("organizer"),
        categories=event_data.get("categories"),
        district=event_data.get("district"),
        image_url=event_data.get("image_url"),
        source_url=event_data.get("source_url") or event_data.get("detail_url"),
        detail_url=event_data.get("detail_url"),
        ticket_url=event_data.get("ticket_url"),
        source_id=source_id,
        source_event_id=source_event_id,
        region=region,
        dedup_hash=dedup_hash,
        is_active=True,
        first_seen_at=datetime.utcnow(),
        last_seen_at=datetime.utcnow(),
        last_scraped_at=datetime.utcnow(),
    )
    categorize_event(event)
    if event.image_url:
        event.image_source = "original"
    if event.description:
        event.description_source = "scraped"

    if _is_too_long_exhibition(event) or not _has_at_least_one_key_field(event):
        return "skipped", None

    event.completeness = event.calculate_completeness()
    db_session.add(event)
    db_session.flush()
    return "new", event


def mark_stale_events(db_session, source_id: str, scrape_started_at: datetime) -> int:
    """
    Po koncu scrape-a označi vse aktivne dogodke iz tega vira, ki jih scraper
    NI ponovno videl (last_seen_at < scrape_started_at), kot is_active=False.

    Pomembno: NE briše. Samo skrije iz dashboarda. Statusi v event_media,
    history v event_edits ostanejo.
    """
    affected = db_session.query(Event).filter(
        Event.source_id == source_id,
        Event.is_active == True,  # noqa: E712
        Event.last_seen_at < scrape_started_at,
    ).update({"is_active": False}, synchronize_session=False)
    return affected
