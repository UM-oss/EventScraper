"""
Deduplikacija dogodkov — Phase 1 refactor.

Cilji refactorja:
1. Eksplicitno: vsaka odločitev vrne strukturiran rezultat (DedupResult)
   z razlogom in score-om — lahko se posebej beleži v dedup_decisions tabelo.
2. Razširljivo: thresholdi v DedupConfig dataclass — enostavna sprememba
   in testiranje brez spreminjanja logike.
3. Persistent storage: poleg "duplicate" razlikujemo tudi "stale-update"
   (obstoječi event smo našli, posodobimo ga).
"""

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Optional

from rapidfuzz import fuzz

from database.models import Event


# =====================================================================
# KONFIGURACIJA
# =====================================================================

@dataclass
class DedupConfig:
    """Centralizirana konfiguracija deduplikacije.

    Vrednosti so bile preverjene na realnih duplikatih iz baze.
    Sprememba enega thresholda → poženi tests/test_dedup.py.
    """
    # Threshold-i (0-100)
    threshold_same_time: int = 60
    # ko se datum + čas natančno ujemata (lokacija je sekundarna)

    threshold_same_loc: int = 70
    # ko se datum + lokacija ujemata, čas pa ne (en je morda brez ure)

    threshold_title_only: int = 80
    # ko nimamo niti časa niti lokacije za primerjavo

    location_match_threshold: int = 70
    # partial_ratio dveh lokacij — pod tem ju štejemo za RAZLIČNI

    @classmethod
    def from_env(cls):
        """Naloži konfiguracijo iz okoljskih spremenljivk (z fallbackom na default)."""
        import os
        return cls(
            threshold_same_time=int(os.environ.get("DEDUP_TH_SAME_TIME", cls.threshold_same_time)),
            threshold_same_loc=int(os.environ.get("DEDUP_TH_SAME_LOC", cls.threshold_same_loc)),
            threshold_title_only=int(os.environ.get("DEDUP_TH_TITLE_ONLY", cls.threshold_title_only)),
            location_match_threshold=int(os.environ.get("DEDUP_TH_LOCATION", cls.location_match_threshold)),
        )


@dataclass
class DedupResult:
    """Rezultat deduplikacije — vrne se za VSAK pregledan dogodek."""
    decision: str  # "new" | "duplicate" | "stale-update"
    reason: str    # human-readable razlog
    score: Optional[float] = None
    threshold: Optional[int] = None
    matched_event_id: Optional[int] = None
    matched_title: Optional[str] = None


# =====================================================================
# NORMALIZACIJA
# =====================================================================

def normalize_text(text: Optional[str]) -> str:
    if not text:
        return ""
    text = text.lower().strip()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def compute_dedup_hash(title: str, date_start, location: Optional[str] = None) -> str:
    """SHA-256 hash normaliziranega naslova + datuma. Lokacija opcijsko."""
    norm_title = normalize_text(title)
    date_str = date_start.isoformat() if date_start else "nodate"
    return hashlib.sha256(f"{norm_title}|{date_str}".encode("utf-8")).hexdigest()


# =====================================================================
# CORE DEDUPLIKACIJA
# =====================================================================

def find_existing_event(db_session, source_id: str, source_event_id: Optional[str]) -> Optional[Event]:
    """
    Persistent lookup: najprej preveri, ali smo dogodek iz tega vira že imeli
    (po (source_id, source_event_id) unique constraint). Če ja, vrnemo ga
    za UPDATE namesto novega INSERT-a.
    """
    if not source_event_id:
        return None
    return db_session.query(Event).filter(
        Event.source_id == source_id,
        Event.source_event_id == source_event_id,
    ).first()


def check_dedup(
    db_session,
    title: str,
    date_start,
    time_start: Optional[str] = None,
    location: Optional[str] = None,
    config: Optional[DedupConfig] = None,
) -> DedupResult:
    """
    Glavna funkcija deduplikacije. Vrne DedupResult z razlago odločitve.

    Hierarhija:
    1. Brez datuma → ne moremo presoditi → vrnemo "new"
    2. Identičen normaliziran naslov + isti datum → DUPLIKAT
    3. Isti datum + ISTI ČAS:
       - Različni eksplicitni lokaciji → kandidat preskočen
       - Naslov >= threshold_same_time (60%) → DUPLIKAT
    4. Isti datum + ČAS NE UJEMA:
       - Naslov >= threshold_title_only (80%) IN (lokaciji ujema ALI vsaj ena manjka)
         → DUPLIKAT
    """
    cfg = config or DedupConfig()

    if not date_start:
        return DedupResult(decision="new", reason="no_date_to_compare")

    norm_title = normalize_text(title)
    norm_location = normalize_text(location) if location else ""

    candidates = db_session.query(Event).filter(
        Event.date_start == date_start,
    ).all()

    for cand in candidates:
        cand_norm_title = normalize_text(cand.title)
        cand_norm_loc = normalize_text(cand.location) if cand.location else ""

        # 1. Identičen naslov
        if norm_title and norm_title == cand_norm_title:
            return DedupResult(
                decision="duplicate",
                reason="exact_normalized_title",
                score=100.0,
                threshold=100,
                matched_event_id=cand.id,
                matched_title=cand.title,
            )

        title_ratio = max(
            fuzz.ratio(norm_title, cand_norm_title),
            fuzz.partial_ratio(norm_title, cand_norm_title),
            fuzz.token_sort_ratio(norm_title, cand_norm_title),
            fuzz.token_set_ratio(norm_title, cand_norm_title),
        )

        time_match = (
            time_start and cand.time_start
            and time_start[:5] == cand.time_start[:5]
        )

        if time_match:
            # Pri istem datumu+času je čas tako močan signal,
            # da različno zapisana lokacija (venue vs organizer) ne sme blokirati.
            # ČS Rožnik vs ČS Posavje je edge-case ki ga rešimo z urednikovim "Preskoči".
            if title_ratio >= cfg.threshold_same_time:
                return DedupResult(
                    decision="duplicate",
                    reason=f"fuzzy_same_time_t{int(title_ratio)}",
                    score=title_ratio,
                    threshold=cfg.threshold_same_time,
                    matched_event_id=cand.id,
                    matched_title=cand.title,
                )
        else:
            loc_match = None
            if norm_location and cand_norm_loc:
                loc_ratio = fuzz.partial_ratio(norm_location, cand_norm_loc)
                loc_match = loc_ratio >= cfg.location_match_threshold

            if loc_match is False:
                continue  # različni lokaciji + drugačen čas = drug dogodek

            # Stroga zahteva: ko ni časa, mora biti naslov zelo podoben
            if title_ratio >= cfg.threshold_title_only:
                return DedupResult(
                    decision="duplicate",
                    reason=f"fuzzy_title_only_t{int(title_ratio)}",
                    score=title_ratio,
                    threshold=cfg.threshold_title_only,
                    matched_event_id=cand.id,
                    matched_title=cand.title,
                )

    return DedupResult(decision="new", reason="no_match_found")


# =====================================================================
# COMPATIBILITY API (za obstoječ engine, dokler ga ne posodobim)
# =====================================================================

def is_duplicate(db_session, dedup_hash: str) -> bool:
    """Hitra hash-only preverba. Obdrženo zaradi backward compatibility."""
    return db_session.query(Event).filter(Event.dedup_hash == dedup_hash).first() is not None


def is_duplicate_fuzzy(
    db_session, title, date_start,
    time_start=None, location=None, threshold=80,
):
    """Backward-compatible wrapper. Vrne bool. Za novo kodo uporabi check_dedup()."""
    cfg = DedupConfig(threshold_title_only=threshold)
    result = check_dedup(db_session, title, date_start, time_start, location, cfg)
    return result.decision == "duplicate"


def find_fuzzy_duplicates(db_session, title, date_start, threshold=85):
    """Vrne seznam kandidatov za fuzzy duplikate (za ročni pregled)."""
    if not date_start:
        return []
    candidates = db_session.query(Event).filter(Event.date_start == date_start).all()
    norm_title = normalize_text(title)
    out = []
    for cand in candidates:
        cand_title = normalize_text(cand.title)
        ratio = fuzz.ratio(norm_title, cand_title)
        if ratio >= threshold:
            out.append({"event": cand, "similarity": ratio})
    return out


def check_against_published(title, date_start, published_events, threshold=80):
    """Preveri ali je dogodek že objavljen na portalu."""
    if not published_events:
        return False
    norm_title = normalize_text(title)
    date_str = date_start.isoformat() if date_start else ""
    for pub in published_events:
        pub_title = normalize_text(pub.get("title", ""))
        pub_date = pub.get("date_start", "")
        pub_date_str = pub_date if isinstance(pub_date, str) else (pub_date.isoformat() if pub_date else "")
        if date_str != pub_date_str:
            continue
        ratio = max(
            fuzz.ratio(norm_title, pub_title),
            fuzz.partial_ratio(norm_title, pub_title),
            fuzz.token_sort_ratio(norm_title, pub_title),
        )
        if ratio >= threshold:
            return True
    return False
