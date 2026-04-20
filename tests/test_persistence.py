"""
Testi za persistent storage upsert + mark-stale.
Phase 1 refactor — jedro nove logike.
"""

from datetime import date, datetime, timedelta

import pytest

from database.models import Event, EventEdit
from scraper.persistence import upsert_event, mark_stale_events
from scraper.dedup import DedupConfig


def _data(title, date_start, **kw):
    """Hitri factory za scrape data dict."""
    out = {"title": title, "date_start": date_start, "event_type": "koncert", "location": "Test Hall"}
    out.update(kw)
    return out


# =====================================================================
# UPSERT — NEW
# =====================================================================

def test_upsert_new_event(db_session):
    decision, ev = upsert_event(
        db_session,
        _data("Koncert Siddharte", date(2026, 6, 1), source_event_id="abc"),
        source_id="kulturnik-rss-ljubljana",
        region="ljubljana",
    )
    assert decision == "new"
    assert ev is not None
    assert ev.title == "Koncert Siddharte"
    assert ev.is_active is True
    assert ev.first_seen_at is not None
    assert ev.last_seen_at is not None
    assert ev.version == 1


def test_upsert_skips_past_events(db_session):
    decision, ev = upsert_event(
        db_session,
        _data("Stari dogodek", date.today() - timedelta(days=1)),
        source_id="x", region="ljubljana",
    )
    assert decision == "skipped"


def test_upsert_skips_event_without_key_fields(db_session):
    decision, ev = upsert_event(
        db_session,
        {"title": "Brez podatkov", "date_start": date(2026, 6, 1)},
        source_id="x", region="ljubljana",
    )
    assert decision == "skipped"


def test_upsert_skips_long_exhibition(db_session):
    decision, _ = upsert_event(
        db_session,
        _data("Dolgotrajna razstava",
              date(2026, 6, 1),
              date_end=date(2026, 9, 1),
              event_type="razstava"),
        source_id="x", region="ljubljana",
    )
    assert decision == "skipped"


def test_upsert_keeps_exhibition_opening(db_session):
    decision, _ = upsert_event(
        db_session,
        _data("Odprtje razstave Picasso",
              date(2026, 6, 1),
              date_end=date(2026, 9, 1),
              event_type="razstava"),
        source_id="x", region="ljubljana",
    )
    assert decision == "new"


# =====================================================================
# UPSERT — UPDATE existing
# =====================================================================

def test_upsert_updates_existing_event_by_source_event_id(db_session):
    # Prvi scrape
    upsert_event(db_session,
                 _data("Koncert", date(2026, 6, 1), source_event_id="ev1"),
                 source_id="src1", region="ljubljana")
    db_session.commit()

    first = db_session.query(Event).filter(Event.source_event_id == "ev1").first()
    first_seen = first.first_seen_at
    first_id = first.id

    # Drugi scrape — isti dogodek, posodobljen opis
    decision, ev = upsert_event(db_session,
                                 _data("Koncert", date(2026, 6, 1),
                                       source_event_id="ev1",
                                       description="Nov opis prišel."),
                                 source_id="src1", region="ljubljana")
    assert decision == "updated"
    assert ev.id == first_id  # ISTI dogodek
    assert ev.first_seen_at == first_seen  # ohranjen
    assert ev.description == "Nov opis prišel."
    assert ev.version == 2  # zaradi spremembe naslova/opisa


def test_upsert_does_not_overwrite_manual_description(db_session):
    """Če je urednik ročno napisal opis, scraper ga NE prepiše."""
    upsert_event(db_session,
                 _data("Dogodek", date(2026, 6, 1), source_event_id="m1",
                       description="Originalni opis"),
                 source_id="src1", region="ljubljana")
    db_session.commit()

    ev = db_session.query(Event).filter(Event.source_event_id == "m1").first()
    ev.description = "URODNIŠKO POPRAVLJEN OPIS"
    ev.description_source = "manual"
    db_session.commit()

    # Ponovni scrape
    upsert_event(db_session,
                 _data("Dogodek", date(2026, 6, 1), source_event_id="m1",
                       description="Spet drug opis iz vira"),
                 source_id="src1", region="ljubljana")
    db_session.commit()

    ev2 = db_session.query(Event).filter(Event.source_event_id == "m1").first()
    assert ev2.description == "URODNIŠKO POPRAVLJEN OPIS"


# =====================================================================
# UPSERT — DUPLICATE
# =====================================================================

def test_upsert_detects_fuzzy_duplicate(db_session):
    upsert_event(db_session,
                 _data("Bass Fighters pres. Ed Rush", date(2026, 6, 1),
                       time_start="21:00", location="Gustaf"),
                 source_id="src1", region="maribor")
    db_session.commit()

    decision, _ = upsert_event(db_session,
                                _data("Ed Rush (UK) v Mariboru – Drum & Bass večer",
                                      date(2026, 6, 1), time_start="21:00",
                                      location="Bass Fighters"),
                                source_id="src2", region="maribor")
    assert decision == "duplicate"


# =====================================================================
# MARK STALE
# =====================================================================

def test_mark_stale_events(db_session):
    """Dogodki ki jih scraper ne najde več, dobijo is_active=False."""
    # Prvi scrape: ustvari A in B
    upsert_event(db_session,
                 _data("Dogodek A", date(2026, 6, 1), source_event_id="a"),
                 source_id="src1", region="ljubljana")
    upsert_event(db_session,
                 _data("Dogodek B", date(2026, 6, 2), source_event_id="b"),
                 source_id="src1", region="ljubljana")
    db_session.commit()

    # Simulacija drugega scrape-a: scrape_started_at PRED upsert klicem
    import time
    time.sleep(0.05)  # malo počakamo da last_seen razlikuje
    new_scrape_started = datetime.utcnow()
    time.sleep(0.05)

    upsert_event(db_session,
                 _data("Dogodek A", date(2026, 6, 1), source_event_id="a"),
                 source_id="src1", region="ljubljana")
    db_session.commit()

    affected = mark_stale_events(db_session, "src1", new_scrape_started)
    db_session.commit()

    assert affected == 1
    a = db_session.query(Event).filter(Event.source_event_id == "a").first()
    b = db_session.query(Event).filter(Event.source_event_id == "b").first()
    assert a.is_active is True
    assert b.is_active is False


def test_mark_stale_does_not_delete(db_session):
    """Stale dogodki obstajajo še naprej — z editorial statusi."""
    upsert_event(db_session,
                 _data("Stari dogodek", date(2026, 6, 1), source_event_id="z"),
                 source_id="src1", region="ljubljana")
    db_session.commit()

    mark_stale_events(db_session, "src1", datetime.utcnow() + timedelta(seconds=10))
    db_session.commit()

    # Še vedno v bazi
    assert db_session.query(Event).filter(Event.source_event_id == "z").count() == 1
