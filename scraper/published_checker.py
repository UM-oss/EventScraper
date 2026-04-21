"""
Preverja že objavljene dogodke na naših portalih (calendar pages).
Po scrape-u nove dogodke, ki se ujemajo z že objavljenimi, samodejno
označi z statusom "published" — ne pojavijo se več v "Novi" filtru.
"""

import logging
import re
import requests
from datetime import date, timedelta
from bs4 import BeautifulSoup

# cloudscraper premosti Cloudflare blokiranje na *info portalih
try:
    import cloudscraper
    HAS_CLOUDSCRAPER = True
except ImportError:
    HAS_CLOUDSCRAPER = False

from scraper.dedup import normalize_text, check_against_published

logger = logging.getLogger("scraper")


# Mapiranje media_id (kot v media.yaml) → URL koledarja portala
PORTAL_CALENDARS = {
    "sobotainfo":     "https://sobotainfo.com/dogodki",
    "pomurec":        "https://www.pomurec.com/go/189/KOLEDAR_DOGODKOV",
    "mariborinfo":    "https://mariborinfo.com/dogodki",
    "ptujinfo":       "https://ptujinfo.com/dogodki",
    "ljubljanainfo":  "https://ljubljanainfo.com/dogodki",
    "gorenjskainfo":  "https://gorenjskainfo.com/dogodki",
    "dolenjskainfo":  "https://dolenjskainfo.com/dogodki",
}

# *info portali uporabljajo enak Drupal template (Tailwind grid).
# Pomurec ima drug stari portal — parser fallback.

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

DEFAULT_HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "sl-SI,sl;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


class PublishedChecker:
    """Preverja že objavljene dogodke."""

    def __init__(self, max_pages: int = 5):
        # Cloudscraper premosti Cloudflare zaščito (potreben za *info portale)
        if HAS_CLOUDSCRAPER:
            self.session = cloudscraper.create_scraper(
                browser={"browser": "chrome", "platform": "darwin", "mobile": False}
            )
            logger.debug("PublishedChecker uses cloudscraper")
        else:
            self.session = requests.Session()
            logger.warning("cloudscraper ni nameščen, uporabljam navadni requests")
        self.session.headers.update(DEFAULT_HEADERS)
        self._cache = {}
        self.max_pages = max_pages

    # ---------------- PARSERS ----------------

    def _parse_drupal_info(self, html, source_label):
        """*info portali (Drupal Tailwind template)."""
        soup = BeautifulSoup(html, "html.parser")
        events = []
        for article in soup.select("article.grid"):
            # Naslov: section > h2 > a
            title_el = article.select_one("section h2 a")
            title = title_el.get_text(strip=True) if title_el else ""

            # Datum: <time datetime="2026-04-19CEST10:04:00">
            event_date = None
            time_el = article.select_one("time")
            if time_el:
                dt_attr = time_el.get("datetime", "")
                m = re.match(r"(\d{4}-\d{2}-\d{2})", dt_attr)
                if m:
                    try:
                        event_date = date.fromisoformat(m.group(1))
                    except ValueError:
                        pass

            # Lokacija (opcijsko)
            loc_el = article.select_one("section .font-sans.font-bold")
            location = ""
            if loc_el:
                location = loc_el.get_text(separator=" ", strip=True)
                # Odstrani datum iz lokacije
                if event_date:
                    location = location.replace(time_el.get_text(strip=True), "").strip()

            if title and event_date:
                events.append({
                    "title": title,
                    "date_start": event_date,
                    "location": location,
                    "source_portal": source_label,
                })
        return events

    def _parse_pomurec(self, html, source_label):
        """Pomurec (stari portal)."""
        soup = BeautifulSoup(html, "html.parser")
        events = []
        # Pomurec strukture: probaj nekaj selektorjev
        for sel in [".event-item", ".dogodek", "tr.row", ".koledar-row"]:
            items = soup.select(sel)
            if items:
                for item in items:
                    title_el = item.select_one("a.title, h3, h2, td.title")
                    title = title_el.get_text(strip=True) if title_el else ""
                    # Datum iščemo z regex iz besedila
                    text = item.get_text(" ", strip=True)
                    date_match = re.search(r"(\d{1,2})\.\s*(\d{1,2})\.\s*(20\d{2})", text)
                    event_date = None
                    if date_match:
                        try:
                            event_date = date(int(date_match.group(3)),
                                               int(date_match.group(2)),
                                               int(date_match.group(1)))
                        except ValueError:
                            pass
                    if title and event_date:
                        events.append({
                            "title": title,
                            "date_start": event_date,
                            "source_portal": source_label,
                        })
                break
        return events

    # ---------------- FETCH ----------------

    def _fetch_paginated(self, base_url, parser):
        """Pridobi vse strani (do max_pages) za en portal."""
        all_events = []
        seen_titles = set()
        for page in range(self.max_pages):
            sep = "&" if "?" in base_url else "?"
            url = base_url if page == 0 else f"{base_url}{sep}page={page}"
            try:
                resp = self.session.get(url, timeout=15)
                if resp.status_code != 200:
                    break
                events = parser(resp.text, base_url)
                if not events:
                    break
                # Dedup po (title, date) da ne podvajamo
                new_count = 0
                for ev in events:
                    key = (normalize_text(ev["title"]), ev["date_start"].isoformat())
                    if key not in seen_titles:
                        seen_titles.add(key)
                        all_events.append(ev)
                        new_count += 1
                if new_count == 0:
                    break  # ista stran kot prej (paginacija končana)
            except Exception as e:
                logger.warning(f"  Page fetch error {url}: {e}")
                break
        return all_events

    def fetch_published_events(self, media_id):
        """Vrne seznam že objavljenih dogodkov za specifičen medij (cached)."""
        if media_id in self._cache:
            return self._cache[media_id]

        url = PORTAL_CALENDARS.get(media_id)
        if not url:
            self._cache[media_id] = []
            return []

        # Izberi parser glede na portal
        parser = self._parse_pomurec if media_id == "pomurec" else self._parse_drupal_info

        events = self._fetch_paginated(url, parser)
        # Filtriraj samo prihodnje
        cutoff = date.today() - timedelta(days=1)
        events = [e for e in events if e["date_start"] >= cutoff]
        self._cache[media_id] = events
        logger.info(f"  Portal '{media_id}': {len(events)} že objavljenih dogodkov")
        return events

    def is_already_published(self, title, date_start, media_id):
        """Preveri če dogodek z naslovom+datumom že obstaja na portalu."""
        published = self.fetch_published_events(media_id)
        if not published:
            return False
        return check_against_published(title, date_start, published)

    def check_all_portals(self):
        """Predpomnimo objavljene dogodke za vse portale na začetku scrapinga."""
        total = 0
        for media_id in PORTAL_CALENDARS:
            try:
                events = self.fetch_published_events(media_id)
                total += len(events)
            except Exception as e:
                logger.warning(f"  Napaka pri preverjanju portala {media_id}: {e}")
        logger.info(f"  Skupaj {total} že objavljenih dogodkov na vseh portalih")
        return total

    def reset_cache(self):
        """Ponastavi cache (npr. pred novim scrape ciklom)."""
        self._cache = {}
