"""
Preverja že objavljene dogodke na naših portalih preko RSS feed-ov.

Vsak portal izpostavlja /dogodki.rss z dogodki vključno z datumom v
<time datetime="..."> elementu znotraj <description>.

RSS feed-i NISO blokirani s strani Cloudflare WAF (za razliko od HTML
calendar strani), zato delujejo tudi z Render IP-jev.
"""

import logging
import re
from datetime import date, datetime, timedelta

import feedparser
import requests
from bs4 import BeautifulSoup

from scraper.dedup import normalize_text, check_against_published

logger = logging.getLogger("scraper")


# Mapiranje media_id (kot v media.yaml) → URL RSS feed-a portala
PORTAL_FEEDS = {
    "sobotainfo":     "https://sobotainfo.com/dogodki.rss",
    "mariborinfo":    "https://mariborinfo.com/dogodki.rss",
    "ptujinfo":       "https://ptujinfo.com/dogodki.rss",
    "ljubljanainfo":  "https://ljubljanainfo.com/dogodki.rss",
    "gorenjskainfo":  "https://gorenjskainfo.com/dogodki.rss",
    "dolenjskainfo":  "https://dolenjskainfo.com/dogodki.rss",
}

# Backward compat — staro ime za zunanjo kodo
PORTAL_CALENDARS = PORTAL_FEEDS

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

DEFAULT_HEADERS = {
    "User-Agent": UA,
    "Accept": "application/rss+xml,application/xml,text/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "sl-SI,sl;q=0.9,en;q=0.8",
}

# Regex za extractanje datuma iz <time datetime="2026-04-22T14:30:00Z">
RE_TIME_DATETIME = re.compile(r'<time[^>]*datetime="([\d-]{10})')


class PublishedChecker:
    """Preverja že objavljene dogodke na *info portalih preko RSS feed-ov."""

    def __init__(self, max_pages: int = 1):
        # max_pages za RSS ne potrebujemo (vsak feed že ima vse v eni odgovor),
        # ampak ohranimo parameter za backward compat z obstoječimi klici.
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        self._cache = {}
        self.max_pages = max_pages

    def _parse_rss(self, xml_text, source_label):
        """Izvleci dogodke iz Drupal RSS feed-a *info portala.

        Format:
          <item>
            <title>Naslov</title>
            <link>...</link>
            <description>...&lt;time datetime="2026-04-22T14:30:00Z"&gt;...</description>
          </item>
        """
        feed = feedparser.parse(xml_text)
        events = []

        for entry in feed.entries:
            title = (entry.get("title") or "").strip()
            if not title:
                continue

            # Datum: poišči v summary/description preko regex (najhitreje)
            summary = entry.get("summary") or entry.get("description") or ""
            event_date = None

            m = RE_TIME_DATETIME.search(summary)
            if m:
                try:
                    event_date = date.fromisoformat(m.group(1))
                except ValueError:
                    pass

            # Fallback: poišči v summary slovenski format "22.4.2026"
            if not event_date:
                m2 = re.search(r'(\d{1,2})\.\s*(\d{1,2})\.\s*(20\d{2})', summary)
                if m2:
                    try:
                        event_date = date(int(m2.group(3)), int(m2.group(2)), int(m2.group(1)))
                    except ValueError:
                        pass

            if not event_date:
                continue  # brez datuma ne moremo deduplicirati

            # Lokacija: izvleci iz "Prizorišče: ..." vzorca
            location = ""
            loc_match = re.search(r'Prizori[šs]?če:\s*</strong>\s*([^<\n]+)', summary)
            if loc_match:
                location = loc_match.group(1).strip()

            events.append({
                "title": title,
                "date_start": event_date,
                "location": location,
                "link": entry.get("link", ""),
                "source_portal": source_label,
            })

        return events

    def fetch_published_events(self, media_id):
        """Vrne seznam že objavljenih dogodkov za specifičen medij (cached)."""
        if media_id in self._cache:
            return self._cache[media_id]

        url = PORTAL_FEEDS.get(media_id)
        if not url:
            self._cache[media_id] = []
            return []

        try:
            resp = self.session.get(url, timeout=20)
            if resp.status_code != 200:
                logger.warning(f"  Portal '{media_id}' RSS HTTP {resp.status_code}")
                self._cache[media_id] = []
                return []
            events = self._parse_rss(resp.text, media_id)
        except Exception as e:
            logger.warning(f"  Portal '{media_id}' RSS fetch failed: {e}")
            self._cache[media_id] = []
            return []

        # Filtriraj samo prihodnje (in zadnji teden, da ujamemo "danes")
        cutoff = date.today() - timedelta(days=7)
        events = [e for e in events if e["date_start"] >= cutoff]
        self._cache[media_id] = events
        logger.info(f"  Portal '{media_id}': {len(events)} že objavljenih dogodkov (RSS)")
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
        for media_id in PORTAL_FEEDS:
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
