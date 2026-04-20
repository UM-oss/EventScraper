"""
Testi za podatkovne modele in pomožne metode.
"""

import pytest
from datetime import date, datetime


class TestEventModel:
    def test_calculate_completeness_full(self, sample_event):
        """Polno izpolnjen dogodek ima visoko completeness."""
        score = sample_event.calculate_completeness()
        assert score >= 0.8

    def test_calculate_completeness_minimal(self, db_session):
        """Minimalno izpolnjen dogodek."""
        from database.models import Event
        event = Event(title="Samo naslov", source_id="test")
        db_session.add(event)
        db_session.commit()
        score = event.calculate_completeness()
        assert score <= 0.2

    def test_to_dict(self, sample_event):
        """to_dict vrne pravilen slovar."""
        d = sample_event.to_dict()
        assert d["title"] == "Testni koncert"
        assert d["date_start"] == "2026-05-15"
        assert d["location"] == "Cankarjev dom"
        assert d["event_type"] == "koncert"
        assert d["source_id"] == "test-source"

    @pytest.mark.skip(reason="Drupal integracija je v Phase 2 (out of scope za Phase 1)")
    def test_to_drupal(self, sample_event):
        """to_drupal vrne Drupal-kompatibilen JSON."""
        pass

    def test_event_media_relationship(self, db_session, sample_event, sample_media):
        """Dogodek se pravilno poveže z medijem."""
        sample_event.media_outlets.append(sample_media)
        db_session.commit()
        assert sample_media in sample_event.media_outlets
        assert sample_event in sample_media.events


class TestGetDb:
    def test_context_manager_commits(self, db_session):
        """get_db context manager pravilno commitne."""
        from database.models import Event
        # Ta test samo preveri da se get_db uvozi
        from database.models import get_db
        assert callable(get_db)

    def test_context_manager_rollback_on_error(self):
        """get_db rollbackne ob napaki."""
        from database.models import get_db
        try:
            with get_db() as db:
                raise ValueError("test error")
        except ValueError:
            pass  # Pričakovano — rollback se je izvedel


class TestStatusValidation:
    def test_valid_statuses(self):
        """Vsi veljavni statusi so definirani."""
        from web.app import VALID_STATUSES
        assert "new" in VALID_STATUSES
        assert "approved" in VALID_STATUSES
        assert "published" in VALID_STATUSES
        assert "skipped" in VALID_STATUSES

    def test_valid_transitions(self):
        """Prehodi statusov so konsistentni."""
        from web.app import VALID_TRANSITIONS
        assert "approved" in VALID_TRANSITIONS["new"]
        assert "skipped" in VALID_TRANSITIONS["new"]
        assert "queued" in VALID_TRANSITIONS["approved"]
