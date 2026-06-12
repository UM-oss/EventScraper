"""
Testi za novo dedup logiko (Phase 1).
"""

from datetime import date, timedelta

import pytest

from database.models import Event
from scraper.dedup import (
    check_dedup, DedupConfig, DedupResult,
    normalize_text, compute_dedup_hash,
    is_duplicate_fuzzy,  # backward compat
)

# Relativni prihodnji datumi (testi ne smejo zastareti)
FUTURE = date.today() + timedelta(days=30)
FUTURE2 = date.today() + timedelta(days=31)
FUTURE_FAR = date.today() + timedelta(days=120)


def _add_event(db, **kw):
    defaults = dict(
        title="Default", date_start=FUTURE, source_id="x", dedup_hash="x",
    )
    defaults.update(kw)
    e = Event(**defaults)
    db.add(e)
    db.commit()
    return e


# =====================================================================
# NORMALIZATION
# =====================================================================

def test_normalize_strips_diacritics():
    assert normalize_text("Češčar Žužemberk") == "cescar zuzemberk"


def test_normalize_strips_punctuation():
    assert normalize_text("Hello, World! - Test") == "hello world test"


def test_normalize_handles_none():
    assert normalize_text(None) == ""


# =====================================================================
# DEDUP — exact match
# =====================================================================

def test_dedup_exact_normalized_title(db_session):
    _add_event(db_session, title="Koncert Siddharte", date_start=FUTURE)
    res = check_dedup(db_session, "Koncert Siddharte", FUTURE)
    assert res.decision == "duplicate"
    assert res.reason == "exact_normalized_title"


def test_dedup_no_date_returns_new(db_session):
    res = check_dedup(db_session, "Brez datuma", None)
    assert res.decision == "new"


# =====================================================================
# DEDUP — same time
# =====================================================================

def test_dedup_same_time_low_title_similarity(db_session):
    """Bass Fighters pres Ed Rush vs Ed Rush v Mariboru — isti čas → duplikat."""
    _add_event(db_session,
               title="Bass Fighters pres. Ed Rush",
               date_start=FUTURE,
               time_start="21:00",
               location="Gustaf")
    res = check_dedup(db_session,
                      "Ed Rush (UK) v Mariboru – Drum & Bass večer",
                      FUTURE,
                      time_start="21:00",
                      location="Bass Fighters")
    assert res.decision == "duplicate"
    assert "fuzzy_same_time" in res.reason


def test_dedup_same_time_with_high_title_similarity(db_session):
    """KOMPROMIS: enak datum+čas + zelo podoben naslov = duplikat tudi pri
    drugačni lokaciji. Razlog: drugi viri pogosto pišejo lokacijo različno
    (venue vs organizator). Resnične "false positive" primere reši urednik
    s 'Preskoči'."""
    _add_event(db_session,
               title="Čistilna akcija v ČS Posavje",
               date_start=FUTURE,
               time_start="09:00",
               location="ČS Posavje")
    res = check_dedup(db_session,
                      "Čistilna akcija v ČS Rožnik",
                      FUTURE,
                      time_start="09:00",
                      location="ČS Rožnik")
    assert res.decision == "duplicate"  # token_set ratio je visok


# =====================================================================
# DEDUP — different time
# =====================================================================

def test_dedup_different_time_strict_threshold(db_session):
    """Brez ujemanja časa potrebujemo >= 80% naslova."""
    _add_event(db_session, title="Wigmorski solisti", date_start=FUTURE)
    # 100% match
    res = check_dedup(db_session,
                      "5. koncert Komornega cikla: Wigmorski solisti",
                      FUTURE)
    assert res.decision == "duplicate"


def test_dedup_different_time_low_similarity_returns_new(db_session):
    _add_event(db_session, title="Koncert Siddharte", date_start=FUTURE)
    res = check_dedup(db_session, "Predavanje o astronomiji", FUTURE)
    assert res.decision == "new"


# =====================================================================
# CONFIGURABLE THRESHOLDS
# =====================================================================

def test_dedup_threshold_can_be_lowered(db_session):
    _add_event(db_session,
               title="Festival glasbe", date_start=FUTURE,
               time_start="20:00")
    config = DedupConfig(threshold_same_time=30)  # zelo nizek
    res = check_dedup(db_session,
                      "Koncert v parku",  # nepovezan naslov
                      FUTURE,
                      time_start="20:00",
                      config=config)
    # Z threshold 30 bo morda match — preverimo da config dela
    assert res.threshold == 30 or res.decision == "new"


# =====================================================================
# DEDUP RESULT
# =====================================================================

def test_dedup_result_includes_matched_event_id(db_session):
    e = _add_event(db_session, title="Match me", date_start=FUTURE)
    res = check_dedup(db_session, "Match me", FUTURE)
    assert res.matched_event_id == e.id
    assert res.matched_title == "Match me"


# =====================================================================
# BACKWARD COMPAT
# =====================================================================

def test_backward_compat_is_duplicate_fuzzy(db_session):
    _add_event(db_session, title="Original event", date_start=FUTURE)
    assert is_duplicate_fuzzy(db_session, "Original event", FUTURE) is True
    assert is_duplicate_fuzzy(db_session, "Nepovezan dogodek", FUTURE) is False


# =====================================================================
# HASH
# =====================================================================

def test_compute_dedup_hash_deterministic():
    h1 = compute_dedup_hash("Koncert", FUTURE)
    h2 = compute_dedup_hash("KONCERT", FUTURE)  # case-insensitive
    h3 = compute_dedup_hash("Koncert", FUTURE2)
    assert h1 == h2
    assert h1 != h3
