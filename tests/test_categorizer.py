"""
Testi za kategorizacijo dogodkov.
"""

import pytest
from scraper.categorizer import categorize_event_type, categorize_target_audience


class TestCategorizeEventType:
    def test_koncert(self):
        assert categorize_event_type("Koncert Siddharte") == "koncert"

    def test_razstava(self):
        assert categorize_event_type("Razstava sodobne umetnosti") == "razstava"

    def test_film(self):
        assert categorize_event_type("Filmska projekcija: Kino pod zvezdami") == "film"

    def test_gledalisce(self):
        assert categorize_event_type("Gledališka predstava Hamlet") == "gledalisce"

    def test_delavnica(self):
        assert categorize_event_type("Kreativna delavnica za otroke") == "delavnica"

    def test_festival(self):
        assert categorize_event_type("Festival Lent 2026") == "festival"

    def test_sport(self):
        assert categorize_event_type("Maraton treh src") == "sport"

    def test_unknown(self):
        result = categorize_event_type("Dopis o storitvi XYZ")
        assert result is None or result == "nekategorizirano"


class TestCategorizeTargetAudience:
    def test_otroci(self):
        result = categorize_target_audience("Delavnica za otroke")
        assert "otroci" in result or "druzine" in result

    def test_default_vsi(self):
        result = categorize_target_audience("Splošen dogodek")
        assert result is None or result == "vsi"
