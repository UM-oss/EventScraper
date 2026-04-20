"""
Bazni razred za vse parserje.
Vsebuje skupne utilite: extract_text, extract_attr, parse_date, parse_time, resolve_url.
"""

import re
from datetime import date, datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from dateutil import parser as date_parser

# Slovenski meseci
SI_MONTHS = {
    "januar": 1, "februar": 2, "marec": 3, "april": 4,
    "maj": 5, "junij": 6, "julij": 7, "avgust": 8,
    "september": 9, "oktober": 10, "november": 11, "december": 12
}

SI_MONTHS_SHORT = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4,
    "maj": 5, "jun": 6, "jul": 7, "avg": 8,
    "sep": 9, "okt": 10, "nov": 11, "dec": 12
}


class BaseParser:
    """Bazni razred za parserje. Podrazredi implementirajo parse()."""

    def __init__(self, fetcher=None):
        """
        Args:
            fetcher: objekt z metodo fetch_page(url, config) za prenos strani
        """
        self.fetcher = fetcher

    def parse(self, config, html=None):
        """
        Razčleni vir in vrni seznam dict-ov z dogodki.

        Args:
            config: SourceConfig objekt
            html: opcijski HTML (za HTML parserje)

        Returns:
            list[dict]: seznam dogodkov
        """
        raise NotImplementedError

    @property
    def needs_html(self):
        """Ali parser potrebuje predhodno naloženega HTML-ja ali sam pridobi podatke."""
        return True

    @property
    def skip_details(self):
        """Ali parser že vrne dovolj podatkov in ni treba pobiranja podstrani."""
        return False

    # === UTILITE ===

    @staticmethod
    def extract_text(element, selector):
        """Varno izvleci tekst iz HTML elementa."""
        if not selector or not element:
            return None
        for sel in selector.split(","):
            sel = sel.strip()
            found = element.select_one(sel)
            if found:
                return found.get_text(strip=True)
        return None

    @staticmethod
    def extract_attr(element, selector, attr="href"):
        """Varno izvleci atribut iz HTML elementa."""
        if not selector or not element:
            return None
        for sel in selector.split(","):
            sel = sel.strip()
            found = element.select_one(sel)
            if found and found.has_attr(attr):
                return found[attr]
        if not selector and element.has_attr(attr):
            return element[attr]
        return None

    @staticmethod
    def parse_date(date_str):
        """Razčleni datum iz različnih formatov. Vrne (date, date|None)."""
        if not date_str:
            return None, None
        date_str = date_str.strip()

        # Poskusi z dateutil
        try:
            normalized = date_str.lower()
            for si_name, month_num in SI_MONTHS.items():
                if si_name in normalized:
                    normalized = normalized.replace(si_name, str(month_num))
                    break
            parsed = date_parser.parse(normalized, dayfirst=True, fuzzy=True)
            return parsed.date(), None
        except (ValueError, TypeError):
            pass

        # D.M.YYYY format
        match = re.search(r"(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})", date_str)
        if match:
            try:
                d = date(int(match.group(3)), int(match.group(2)), int(match.group(1)))
                return d, None
            except ValueError:
                pass

        return None, None

    @staticmethod
    def parse_time(time_str):
        """Izvleci uro iz besedila. Vrne (start, end|None)."""
        if not time_str:
            return None, None
        match = re.search(r"(\d{1,2}[:.]\d{2})\s*[-–]\s*(\d{1,2}[:.]\d{2})", time_str)
        if match:
            return match.group(1).replace(".", ":"), match.group(2).replace(".", ":")
        match = re.search(r"(\d{1,2}[:.]\d{2})", time_str)
        if match:
            return match.group(1).replace(".", ":"), None
        return None, None

    @staticmethod
    def resolve_url(url, base_url):
        """Pretvori relativni URL v absolutni."""
        if not url:
            return None
        if url.startswith("http"):
            return url
        return urljoin(base_url, url)
