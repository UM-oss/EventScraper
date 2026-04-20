"""
Feed parserji: RSS, Kulturnik RSS, iCal in Manual (no-op).
"""

import logging
import requests
from datetime import date, datetime

from bs4 import BeautifulSoup
from dateutil import parser as date_parser
import feedparser
from icalendar import Calendar as iCalCalendar

from scraper.parsers.base import BaseParser
from scraper.parsers.registry import ParserRegistry

logger = logging.getLogger("scraper")


@ParserRegistry.register("rss")
class RssParser(BaseParser):
    """Univerzalni RSS/Atom parser z občinskimi razširitvami."""

    @property
    def needs_html(self):
        return False

    @property
    def skip_details(self):
        return True

    def parse(self, config, html=None):
        feed_url = config.feed_url or config.list_url
        logger.info(f"  RSS: prebiram feed {feed_url}")

        events_raw = []
        feed = feedparser.parse(feed_url)

        if feed.bozo and not feed.entries:
            logger.warning(f"  RSS: napaka pri parsanju feeda: {feed.bozo_exception}")
            return events_raw

        logger.info(f"  RSS: najdenih {len(feed.entries)} vnosov")

        for entry in feed.entries:
            event = {}
            event["title"] = entry.get("title", "").strip()
            event["detail_url"] = entry.get("link", "")
            event["source_url"] = event["detail_url"]

            # Opis
            desc_html = ""
            if hasattr(entry, "content") and entry.content:
                desc_html = entry.content[0].get("value", "")
            elif hasattr(entry, "summary"):
                desc_html = entry.summary or ""
            elif hasattr(entry, "description"):
                desc_html = entry.description or ""

            if desc_html:
                soup = BeautifulSoup(desc_html, "lxml")
                event["description"] = soup.get_text(separator=" ", strip=True)
                img = soup.find("img")
                if img:
                    src = img.get("src") or img.get("data-src")
                    if src:
                        event["image_url"] = self.resolve_url(src, config.base_url)

            # Datum — občinski RSS imajo startdate kot dict ali string
            start_date_raw = entry.get("startdate", "") or entry.get("start_date", "")
            if start_date_raw:
                if isinstance(start_date_raw, dict):
                    start_date_str = start_date_raw.get("date", "") or start_date_raw.get("string", "")
                else:
                    start_date_str = str(start_date_raw)
                if start_date_str:
                    event["date_start"], _ = self.parse_date(start_date_str)
                    t_start, t_end = self.parse_time(start_date_str)
                    event["time_start"] = t_start
                    event["time_end"] = t_end
            elif hasattr(entry, "published"):
                event["date_start"], _ = self.parse_date(entry.published)
            elif hasattr(entry, "updated"):
                event["date_start"], _ = self.parse_date(entry.updated)

            # Lokacija
            loc_raw = entry.get("location", "")
            if isinstance(loc_raw, dict):
                event["location"] = loc_raw.get("string", "") or loc_raw.get("value", "")
            else:
                event["location"] = str(loc_raw) if loc_raw else ""

            # Kategorije
            if hasattr(entry, "tags") and entry.tags:
                event["categories"] = ", ".join(
                    tag.get("term", "") for tag in entry.tags if tag.get("term")
                )
            elif entry.get("category"):
                event["categories"] = entry.get("category")

            # Slika
            if not event.get("image_url"):
                if hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
                    event["image_url"] = entry.media_thumbnail[0].get("url", "")
                elif hasattr(entry, "enclosures") and entry.enclosures:
                    for enc in entry.enclosures:
                        if enc.get("type", "").startswith("image/"):
                            event["image_url"] = enc.get("href", "")
                            break
                elif entry.get("image"):
                    event["image_url"] = entry.get("image")

            event["source_event_id"] = entry.get("id", "") or entry.get("guid", "")

            if event.get("title"):
                events_raw.append(event)

        return events_raw


@ParserRegistry.register("kulturnik-rss")
class KulturnikRssParser(BaseParser):
    """Kulturnik.si RSS parser z iCal razširitvami."""

    @property
    def needs_html(self):
        return False

    @property
    def skip_details(self):
        return True

    def parse(self, config, html=None):
        feed_url = config.feed_url or config.list_url
        logger.info(f"  Kulturnik RSS: prebiram feed {feed_url}")

        events_raw = []
        feed = feedparser.parse(feed_url)

        if feed.bozo and not feed.entries:
            logger.warning(f"  Kulturnik RSS: napaka: {feed.bozo_exception}")
            return events_raw

        logger.info(f"  Kulturnik RSS: najdenih {len(feed.entries)} dogodkov")

        for entry in feed.entries:
            event = {}
            event["title"] = entry.get("title", "").strip()
            event["detail_url"] = entry.get("link", "")
            event["source_url"] = event["detail_url"]

            # Datum iz ical:dtstart
            dtstart = entry.get("ical_dtstart", "")
            if dtstart:
                try:
                    dt = date_parser.parse(dtstart)
                    event["date_start"] = dt.date()
                    if dt.hour != 0 or dt.minute != 0:
                        event["time_start"] = f"{dt.hour:02d}:{dt.minute:02d}"
                except (ValueError, TypeError):
                    event["date_start"], _ = self.parse_date(dtstart)

            # Lokacija
            location = entry.get("ical_location", "")
            if location:
                event["location"] = location.replace("\xa0", " ").strip()

            # Slika iz enclosure
            if hasattr(entry, "enclosures") and entry.enclosures:
                for enc in entry.enclosures:
                    enc_type = enc.get("type", "")
                    if enc_type.startswith("image/") or enc.get("href", "").endswith(
                        (".jpg", ".jpeg", ".png", ".gif")
                    ):
                        event["image_url"] = enc.get("href", "")
                        break

            # Organizator — dc_source je ID sistema, ne organizator!
            # Uporabimo dc_publisher če obstaja, sicer pustimo prazno
            dc_publisher = entry.get("dc_publisher", "")
            if dc_publisher:
                event["organizer"] = dc_publisher

            # Kategorije
            if hasattr(entry, "tags") and entry.tags:
                event["categories"] = ", ".join(
                    tag.get("term", "") for tag in entry.tags if tag.get("term")
                )

            event["source_event_id"] = entry.get("id", "") or entry.get("dc_identifier", "")

            if event.get("title"):
                events_raw.append(event)

        return events_raw


@ParserRegistry.register("ical")
class IcalParser(BaseParser):
    """iCal/ICS parser za VEVENT komponente."""

    @property
    def needs_html(self):
        return False

    @property
    def skip_details(self):
        return True

    def parse(self, config, html=None):
        feed_url = config.feed_url or config.list_url
        logger.info(f"  iCal: prebiram feed {feed_url}")

        events_raw = []
        try:
            headers = {"User-Agent": config.user_agent}
            if self.fetcher and hasattr(self.fetcher, 'session'):
                resp = self.fetcher.session.get(feed_url, headers=headers, timeout=config.timeout)
            else:
                resp = requests.get(feed_url, headers=headers, timeout=config.timeout)
            resp.raise_for_status()
            cal = iCalCalendar.from_ical(resp.text)
        except Exception as e:
            logger.error(f"  iCal: napaka pri prenosu/parsanju: {e}")
            return events_raw

        for component in cal.walk():
            if component.name != "VEVENT":
                continue

            event = {}

            summary = component.get("SUMMARY")
            if summary:
                event["title"] = str(summary).strip()

            # Datum začetka
            dtstart = component.get("DTSTART")
            if dtstart:
                dt = dtstart.dt
                if isinstance(dt, datetime):
                    event["date_start"] = dt.date()
                    if dt.hour != 0 or dt.minute != 0:
                        event["time_start"] = f"{dt.hour:02d}:{dt.minute:02d}"
                elif isinstance(dt, date):
                    event["date_start"] = dt

            # Datum konca
            dtend = component.get("DTEND")
            if dtend:
                dt = dtend.dt
                if isinstance(dt, datetime):
                    event["date_end"] = dt.date()
                    if dt.hour != 0 or dt.minute != 0:
                        event["time_end"] = f"{dt.hour:02d}:{dt.minute:02d}"
                elif isinstance(dt, date):
                    event["date_end"] = dt

            # Lokacija
            location = component.get("LOCATION")
            if location:
                event["location"] = str(location).replace("\xa0", " ").strip()

            # Opis
            description = component.get("DESCRIPTION")
            if description:
                desc_text = str(description).strip()
                if "<" in desc_text and ">" in desc_text:
                    desc_soup = BeautifulSoup(desc_text, "html.parser")
                    desc_text = desc_soup.get_text(separator="\n", strip=True)
                event["description"] = desc_text

            # URL
            url = component.get("URL")
            if url:
                event["detail_url"] = str(url)
                event["source_url"] = str(url)

            # Organizator
            organizer = component.get("ORGANIZER")
            if organizer:
                org_str = str(organizer)
                if hasattr(organizer, 'params') and 'CN' in organizer.params:
                    event["organizer"] = str(organizer.params['CN'])
                elif not org_str.startswith("mailto:"):
                    event["organizer"] = org_str

            # Kategorije
            categories = component.get("CATEGORIES")
            if categories:
                if hasattr(categories, 'cats'):
                    event["categories"] = ", ".join(str(c) for c in categories.cats)
                else:
                    event["categories"] = str(categories)

            # UID
            uid = component.get("UID")
            if uid:
                event["source_event_id"] = str(uid)

            # Slika iz ATTACH
            attach = component.get("ATTACH")
            if attach:
                attach_str = str(attach)
                if attach_str.startswith("http") and any(
                    ext in attach_str.lower()
                    for ext in [".jpg", ".jpeg", ".png", ".gif", ".webp"]
                ):
                    event["image_url"] = attach_str

            if event.get("title"):
                events_raw.append(event)

        logger.info(f"  iCal: najdenih {len(events_raw)} dogodkov")
        return events_raw


@ParserRegistry.register("manual")
class ManualParser(BaseParser):
    """Ročni vir — ni avtomatskega scrapinga."""

    @property
    def needs_html(self):
        return False

    @property
    def skip_details(self):
        return True

    def parse(self, config, html=None):
        return []
