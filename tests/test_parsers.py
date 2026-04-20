"""
Testi za parser registry in posamezne parserje.
"""

import pytest
from datetime import date

from scraper.parsers.registry import ParserRegistry, get_parser
from scraper.parsers.base import BaseParser


class TestParserRegistry:
    def test_all_parsers_registered(self):
        """Preveri da so vsi parserji registrirani."""
        import scraper.parsers.html_parser
        import scraper.parsers.feed_parsers
        import scraper.parsers.special_parsers

        parsers = ParserRegistry.list_parsers()
        expected = {
            "html", "rss", "kulturnik-rss", "ical", "manual",
            "kulturnik", "mgml", "kinodvor", "kinosiska",
            "mojaobcina", "cankarjevdom", "visitskofjaloka"
        }
        assert expected.issubset(set(parsers))

    def test_get_parser_by_type(self):
        parser = get_parser("rss")
        assert parser is not None
        assert not parser.needs_html
        assert parser.skip_details

    def test_get_parser_by_source_id(self):
        parser = get_parser("html", source_id="mgml")
        assert parser is not None
        assert parser.__class__.__name__ == "MgmlParser"

    def test_get_parser_unknown(self):
        parser = get_parser("neobstojec-parser")
        assert parser is None

    def test_manual_parser_returns_empty(self):
        parser = get_parser("manual")
        assert parser is not None
        result = parser.parse(None)
        assert result == []


class TestBaseParser:
    def test_parse_date_iso(self):
        d, _ = BaseParser.parse_date("2026-05-15")
        assert d == date(2026, 5, 15)

    def test_parse_date_slovenian(self):
        d, _ = BaseParser.parse_date("15. 5. 2026")
        assert d == date(2026, 5, 15)

    def test_parse_date_slovenian_month(self):
        d, _ = BaseParser.parse_date("15. maj 2026")
        assert d == date(2026, 5, 15)

    def test_parse_date_empty(self):
        d, _ = BaseParser.parse_date("")
        assert d is None

    def test_parse_date_none(self):
        d, _ = BaseParser.parse_date(None)
        assert d is None

    def test_parse_time_range(self):
        start, end = BaseParser.parse_time("20:00 - 22:00")
        assert start == "20:00"
        assert end == "22:00"

    def test_parse_time_single(self):
        start, end = BaseParser.parse_time("ob 19:30")
        assert start == "19:30"
        assert end is None

    def test_parse_time_dot(self):
        start, end = BaseParser.parse_time("19.30")
        assert start == "19:30"

    def test_parse_time_empty(self):
        start, end = BaseParser.parse_time("")
        assert start is None

    def test_resolve_url_absolute(self):
        url = BaseParser.resolve_url("https://example.com/img.jpg", "https://base.com")
        assert url == "https://example.com/img.jpg"

    def test_resolve_url_relative(self):
        url = BaseParser.resolve_url("/img.jpg", "https://base.com/page/")
        assert url == "https://base.com/img.jpg"

    def test_resolve_url_none(self):
        url = BaseParser.resolve_url(None, "https://base.com")
        assert url is None

    def test_extract_text(self):
        from bs4 import BeautifulSoup
        html = '<div><h2 class="title">Naslov</h2><p>Opis</p></div>'
        soup = BeautifulSoup(html, "html.parser")
        assert BaseParser.extract_text(soup, ".title") == "Naslov"
        assert BaseParser.extract_text(soup, ".missing") is None


class TestHtmlParser:
    def test_parse_empty_html(self):
        parser = get_parser("html")

        class FakeConfig:
            list_selectors = {"event_card": ".event"}
            base_url = "https://example.com"

        result = parser.parse(FakeConfig(), html="<html><body></body></html>")
        assert result == []

    def test_parse_with_cards(self):
        parser = get_parser("html")

        class FakeConfig:
            list_selectors = {
                "event_card": ".event",
                "title": "h2",
                "date": ".date",
            }
            base_url = "https://example.com"

        html = """
        <html><body>
            <div class="event">
                <h2>Koncert</h2>
                <span class="date">15. 5. 2026</span>
            </div>
            <div class="event">
                <h2>Razstava</h2>
                <span class="date">20. 5. 2026</span>
            </div>
        </body></html>
        """
        result = parser.parse(FakeConfig(), html=html)
        assert len(result) == 2
        assert result[0]["title"] == "Koncert"
        assert result[1]["title"] == "Razstava"
        assert result[0]["date_start"] == date(2026, 5, 15)
