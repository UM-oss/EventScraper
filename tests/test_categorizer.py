"""
Testi za kategorizacijo dogodkov.
"""

import pytest
from scraper.categorizer import categorize_event_type, categorize_target_audience


class TestCategorizeEventType:
    """8 fiksnih kategorij: glasba, kultura, literatura, predstava,
    sport, sejmi, za otroke, ostalo."""

    def test_glasba(self):
        assert categorize_event_type("Koncert Siddharte") == "glasba"

    def test_kultura_razstava(self):
        assert categorize_event_type("Razstava sodobne umetnosti") == "kultura"

    def test_predstava_film(self):
        assert categorize_event_type("Filmska projekcija: Kino pod zvezdami") == "predstava"

    def test_predstava_gledalisce(self):
        assert categorize_event_type("Gledališka predstava Hamlet") == "predstava"

    def test_kultura_delavnica(self):
        assert categorize_event_type("Kreativna delavnica") == "kultura"

    def test_sport(self):
        assert categorize_event_type("Maraton treh src") == "sport"

    def test_sejmi(self):
        assert categorize_event_type("Veliki bolšji sejem") == "sejmi"

    def test_za_otroke(self):
        assert categorize_event_type("Lutkovna predstava za otroke") == "za otroke"

    def test_literatura(self):
        assert categorize_event_type("Literarni večer in predstavitev knjige") == "literatura"

    def test_unknown_is_ostalo(self):
        # Brez ujemanja → 'ostalo' (vedno vrne nekaj)
        assert categorize_event_type("Dopis o storitvi XYZ") == "ostalo"


class TestCategorizeTargetAudience:
    def test_otroci(self):
        result = categorize_target_audience("Delavnica za otroke")
        assert "otroci" in result or "druzine" in result

    def test_default_vsi(self):
        result = categorize_target_audience("Splošen dogodek")
        assert result is None or result == "vsi"
