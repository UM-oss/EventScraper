"""
Specialni HTML parserji za vire s specifično strukturo.
Vsak parser obravnava unikatne HTML vzorce posameznega vira.
"""

import re
import json
import time
import logging
from datetime import date

from bs4 import BeautifulSoup

from scraper.parsers.base import BaseParser, SI_MONTHS_SHORT
from scraper.parsers.registry import ParserRegistry

logger = logging.getLogger("scraper")


@ParserRegistry.register("kulturnik")
class KulturnikJsonParser(BaseParser):
    """Kulturnik.si — dogodki v <script> tagih kot var e = {...};"""

    @property
    def skip_details(self):
        return True

    def parse(self, config, html=None):
        if not html:
            return []

        soup = BeautifulSoup(html, "lxml")
        events_raw = []
        fields = config.json_fields

        scripts = soup.find_all("script")
        event_count = 0

        for script in scripts:
            text = script.string or ""
            match = re.search(r'var\s+e\s*=\s*(\{.*?\})\s*;', text, re.DOTALL)
            if not match:
                continue
            try:
                item = json.loads(match.group(1))
            except json.JSONDecodeError:
                continue

            event_count += 1
            event = {}
            event["title"] = item.get(fields.get("title", "summary"), "")
            event["description"] = item.get(fields.get("description", "description"), "") or ""
            event["location"] = item.get(fields.get("location", "location"), "")
            event["organizer"] = item.get(fields.get("organizer", "feed_name"), "")
            categories = item.get(fields.get("categories", "categories"), "")
            event["categories"] = categories if isinstance(categories, str) else ""
            event["source_event_id"] = str(item.get(fields.get("event_id", "nid"), ""))

            date_str = item.get(fields.get("date_start", "dbegin"), "")
            event["date_start"], _ = self.parse_date(date_str)
            date_end_str = item.get(fields.get("date_end", "dend"), "")
            if date_end_str:
                event["date_end"], _ = self.parse_date(date_end_str)

            time_raw = item.get(fields.get("time", "hbegin"), "") or ""
            if time_raw and time_raw != "00:00:00":
                event["time_start"] = time_raw[:5] if len(time_raw) >= 5 else time_raw
            event["time_end"] = None

            img = item.get(fields.get("image", "image"), None)
            event["image_url"] = img or None
            if not event["image_url"]:
                icon = item.get("icon", None)
                if icon:
                    event["image_url"] = icon

            url = item.get(fields.get("url", "url"), "")
            event["detail_url"] = url if url else None
            event["source_url"] = url

            if event["title"]:
                events_raw.append(event)

        logger.info(f"  Kulturnik: najdenih {event_count} script blokov, {len(events_raw)} dogodkov")
        return events_raw


@ParserRegistry.register("mgml")
class MgmlParser(BaseParser):
    """MGML — datum v .day/.date/.month div-ih."""

    @property
    def skip_details(self):
        return True

    def parse(self, config, html=None):
        if not html:
            return []

        soup = BeautifulSoup(html, "lxml")
        events_raw = []

        items = soup.select(".event__item")
        logger.info(f"  MGML: najdenih {len(items)} dogodkov")

        for item in items:
            event = {}

            title_el = item.select_one(".event__title a")
            event["title"] = title_el.get_text(strip=True) if title_el else None

            date_num = item.select_one(".event__date .date")
            month_el = item.select_one(".event__date .month")
            if date_num and month_el:
                day = date_num.get_text(strip=True)
                month_text = month_el.get_text(strip=True).lower()
                parts = month_text.split()
                if len(parts) >= 2:
                    month_abbr = parts[0][:3]
                    year = int(parts[-1]) if parts[-1].isdigit() else date.today().year
                    month = SI_MONTHS_SHORT.get(month_abbr)
                    if month and day.isdigit():
                        try:
                            event["date_start"] = date(year, month, int(day))
                        except ValueError:
                            pass

            time_el = item.select_one(".event__time")
            if time_el:
                time_text = time_el.get_text(strip=True).replace("•", "").strip()
                t_start, t_end = self.parse_time(time_text)
                event["time_start"] = t_start
                event["time_end"] = t_end

            loc_el = item.select_one(".event__location")
            event["location"] = loc_el.get_text(strip=True) if loc_el else None

            blurb_el = item.select_one(".event__blurb")
            event["description"] = blurb_el.get_text(strip=True) if blurb_el else None

            type_el = item.select_one(".event__type")
            event["categories"] = type_el.get_text(strip=True) if type_el else None

            img_el = item.select_one("img")
            if img_el:
                img_src = img_el.get("src") or img_el.get("data-src")
                event["image_url"] = self.resolve_url(img_src, config.base_url)

            if title_el and title_el.has_attr("href"):
                event["detail_url"] = self.resolve_url(title_el["href"], config.base_url)

            event["organizer"] = "MGML"

            if event.get("title"):
                events_raw.append(event)

        return events_raw


@ParserRegistry.register("kinodvor")
class KinodvorParser(BaseParser):
    """Kinodvor — dnevi z več projekcijami, slike iz og:image."""

    @property
    def skip_details(self):
        return True

    def parse(self, config, html=None):
        if not html:
            return []

        soup = BeautifulSoup(html, "lxml")
        events_raw = []

        day_wrappers = soup.select(".day-wrappper")
        logger.info(f"  Kinodvor: najdenih {len(day_wrappers)} dni")

        current_year = date.today().year

        for day_wrapper in day_wrappers:
            day_label = day_wrapper.select_one(".day")
            day_date = None
            if day_label:
                day_text = day_label.get_text(strip=True)
                match = re.search(r"(\d{1,2})\.\s*(\d{1,2})\.", day_text)
                if match:
                    try:
                        day_date = date(current_year, int(match.group(2)), int(match.group(1)))
                    except ValueError:
                        pass

            cards = day_wrapper.select(".card-block")
            for card in cards:
                event = {}

                title_el = card.select_one("h6") or card.select_one("h5")
                event["title"] = title_el.get_text(strip=True) if title_el else None
                event["date_start"] = day_date

                time_venue = card.select_one("p.mb-2 b") or card.select_one("p.mb-2 small b")
                if time_venue:
                    tv_text = time_venue.get_text(strip=True)
                    t_start, _ = self.parse_time(tv_text)
                    event["time_start"] = t_start
                    if "/" in tv_text:
                        event["location"] = "Kinodvor, " + tv_text.split("/")[-1].strip()
                    else:
                        event["location"] = "Kinodvor"

                small_els = card.select("p small")
                for small in small_els:
                    parent_p = small.parent
                    if parent_p and "mb-2" not in (parent_p.get("class") or []):
                        event["organizer"] = small.get_text(strip=True)
                        break

                link = card.select_one("a[href*='/film/']")
                if link:
                    event["detail_url"] = link["href"]

                event["categories"] = "Film"

                if event.get("title"):
                    events_raw.append(event)

        logger.info(f"  Kinodvor: skupaj {len(events_raw)} projekcij")

        # Poberi og:image za unikatne filme
        if self.fetcher:
            unique_urls = {}
            for event in events_raw:
                url = event.get("detail_url")
                if url and url not in unique_urls:
                    unique_urls[url.split("?")[0]] = None

            logger.info(f"  Kinodvor: pobiramo slike za {len(unique_urls)} unikatnih filmov...")
            for film_url in unique_urls:
                try:
                    film_html = self.fetcher.fetch_page(film_url, config)
                    if film_html:
                        film_soup = BeautifulSoup(film_html, "lxml")
                        og_img = film_soup.find("meta", property="og:image")
                        if og_img and og_img.get("content"):
                            unique_urls[film_url] = og_img["content"]
                        else:
                            for img in film_soup.find_all("img"):
                                src = img.get("src", "")
                                if src and not any(x in src for x in ["logo", "icon", "banner", "facebook"]):
                                    unique_urls[film_url] = src
                                    break
                    time.sleep(1)
                except Exception as e:
                    logger.warning(f"  Napaka pri sliki za {film_url}: {e}")

            for event in events_raw:
                url = event.get("detail_url")
                if url:
                    img = unique_urls.get(url.split("?")[0])
                    if img:
                        event["image_url"] = img

        return events_raw


@ParserRegistry.register("kinosiska")
class KinoSiskaParser(BaseParser):
    """Kino Šiška — slike v CSS background-image."""

    @property
    def skip_details(self):
        return True

    def parse(self, config, html=None):
        if not html:
            return []

        soup = BeautifulSoup(html, "lxml")
        events_raw = []

        cards = soup.select("[class*='card-event']")
        logger.info(f"  Kino Šiška: najdenih {len(cards)} dogodkov")

        for card in cards:
            event = {}

            title_el = card.select_one(".title")
            event["title"] = title_el.get_text(strip=True) if title_el else None

            time_el = card.select_one(".time")
            if time_el:
                time_text = time_el.get_text(strip=True)
                event["date_start"], _ = self.parse_date(time_text)
                t_start, _ = self.parse_time(time_text)
                event["time_start"] = t_start

            cat_el = card.select_one(".category .background")
            event["categories"] = cat_el.get_text(strip=True) if cat_el else None

            sub_el = card.select_one(".subtitle, .supertitle")
            event["description"] = sub_el.get_text(strip=True) if sub_el else None

            img_div = card.select_one(".image, .grayscale")
            if img_div:
                style = img_div.get("style", "")
                match = re.search(r"url\(['\"]?(.*?)['\"]?\)", style)
                if match:
                    event["image_url"] = match.group(1)

            link = card.select_one("a[href*='/dogodek/']")
            if not link:
                btn = card.select_one("button[onclick]")
                if btn:
                    onclick = btn.get("onclick", "")
                    match = re.search(r"href='(.*?)'", onclick)
                    if match:
                        url = match.group(1).split("?")[0]
                        event["detail_url"] = self.resolve_url(url, config.base_url)
            else:
                event["detail_url"] = self.resolve_url(link["href"], config.base_url)

            event["location"] = "Kino Šiška"
            event["organizer"] = "Kino Šiška"

            if event.get("title"):
                if "text-strikethrough" in " ".join(card.get("class", [])):
                    continue
                events_raw.append(event)

        return events_raw


@ParserRegistry.register("mojaobcina")
class MojaObcinaParser(BaseParser):
    """MojaObcina.si — enak parser za vse regije."""

    @property
    def skip_details(self):
        return True

    def parse(self, config, html=None):
        if not html:
            return []

        soup = BeautifulSoup(html, "lxml")
        events_raw = []

        si_months = {
            "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4,
            "MAJ": 5, "JUN": 6, "JUL": 7, "AVG": 8,
            "SEP": 9, "OKT": 10, "NOV": 11, "DEC": 12
        }

        articles = soup.select("article.kvadrat-vsebine-clean, article.kvadrat-vsebine-cela-vrsta")
        logger.info(f"  MojaObcina: najdenih {len(articles)} dogodkov")

        for article in articles:
            event = {}

            title_el = article.select_one(".kv-naslov a, .kv-naslov")
            event["title"] = title_el.get_text(strip=True) if title_el else None

            dan_el = article.select_one(".kv-dan")
            mesec_el = article.select_one(".kv-mesec")
            leto_el = article.select_one(".kv-leto")
            if dan_el and mesec_el and leto_el:
                try:
                    day = int(dan_el.get_text(strip=True))
                    month_text = mesec_el.get_text(strip=True).upper()
                    year = int(leto_el.get_text(strip=True))
                    month = si_months.get(month_text)
                    if month:
                        event["date_start"] = date(year, month, day)
                except (ValueError, TypeError):
                    pass

            cas_el = article.select_one(".kv-cas")
            if cas_el:
                time_text = cas_el.get_text(strip=True)
                t_start, t_end = self.parse_time(time_text)
                event["time_start"] = t_start
                event["time_end"] = t_end

            loc_el = article.select_one(".kv-lokacija")
            event["location"] = loc_el.get_text(strip=True) if loc_el else None

            cat_el = article.select_one(".kv-kategorija-2")
            event["categories"] = cat_el.get_text(strip=True) if cat_el else None

            price_el = article.select_one(".kv-vstopnina")
            event["price"] = price_el.get_text(strip=True) if price_el else None

            img_el = article.select_one(".kv-slika img")
            if img_el:
                src = img_el.get("src") or img_el.get("data-src")
                event["image_url"] = self.resolve_url(src, config.base_url)

            link_el = article.select_one(".kv-naslov a")
            if link_el and link_el.has_attr("href"):
                event["detail_url"] = self.resolve_url(link_el["href"], config.base_url)

            if event.get("title"):
                events_raw.append(event)

        return events_raw


@ParserRegistry.register("cankarjevdom")
class CankarjevDomParser(BaseParser):
    """Cankarjev dom — hero eventi."""

    @property
    def skip_details(self):
        return True

    def parse(self, config, html=None):
        if not html:
            return []

        soup = BeautifulSoup(html, "lxml")
        events_raw = []

        heroes = soup.select(".hero--event")
        logger.info(f"  Cankarjev dom: najdenih {len(heroes)} hero dogodkov")

        current_year = date.today().year

        for hero in heroes:
            event = {}

            title_el = hero.select_one(".hero--title h2 a, .hero--title a, h2 a")
            event["title"] = title_el.get_text(strip=True) if title_el else None

            if title_el and title_el.has_attr("href"):
                event["detail_url"] = self.resolve_url(title_el["href"], config.base_url)

            date_el = hero.select_one(".hero--date")
            if date_el:
                date_text = date_el.get_text(strip=True)
                match = re.search(r"(\d{1,2})\.\s*(\w+)\.?\s*(\d{1,2}:\d{2})?", date_text)
                if match:
                    day = int(match.group(1))
                    month_text = match.group(2).lower()[:3]
                    month = SI_MONTHS_SHORT.get(month_text)
                    if month:
                        try:
                            event["date_start"] = date(current_year, month, day)
                        except ValueError:
                            pass
                    if match.group(3):
                        event["time_start"] = match.group(3)

            type_el = hero.select_one(".event--type a, .event--type")
            event["categories"] = type_el.get_text(strip=True) if type_el else None

            img_el = hero.select_one(".hero--image img")
            if img_el:
                src = img_el.get("src") or img_el.get("data-src")
                event["image_url"] = self.resolve_url(src, config.base_url)

            event["location"] = "Cankarjev dom"
            event["organizer"] = "Cankarjev dom"

            if event.get("title"):
                events_raw.append(event)

        return events_raw


@ParserRegistry.register("visitskofjaloka")
class VisitSkofjaLokaParser(BaseParser):
    """Visit Škofja Loka — dnevi z več dogodki."""

    @property
    def skip_details(self):
        return True

    def parse(self, config, html=None):
        if not html:
            return []

        soup = BeautifulSoup(html, "lxml")
        events_raw = []

        days = soup.select(".event-list-day")
        logger.info(f"  Visit Škofja Loka: {len(days)} dni")

        for day in days:
            day_date = None
            day_children = [c for c in day.children if hasattr(c, 'name')]
            for child in day_children:
                if child.name != 'div' or 'event-list-item' not in ' '.join(child.get('class', [])):
                    text = child.get_text(strip=True)
                    if text:
                        day_date, _ = self.parse_date(text)
                        if day_date:
                            break

            items = day.select(".event-list-item")
            for item in items:
                event = {}

                title_el = item.select_one(".event-content h2")
                event["title"] = title_el.get_text(strip=True) if title_el else None
                event["date_start"] = day_date

                time_el = item.select_one(".event-time")
                if time_el:
                    time_text = time_el.get_text(strip=True)
                    if time_text and time_text != "po urniku":
                        t_start, t_end = self.parse_time(time_text)
                        event["time_start"] = t_start
                        event["time_end"] = t_end

                loc_el = item.select_one(".event-details-location")
                addr_el = item.select_one(".event-details-address")
                loc_parts = []
                if addr_el:
                    loc_parts.append(addr_el.get_text(strip=True))
                if loc_el:
                    loc_parts.append(loc_el.get_text(strip=True))
                event["location"] = ", ".join(loc_parts) if loc_parts else None

                type_el = item.select_one(".event-details-type")
                event["categories"] = type_el.get_text(strip=True) if type_el else None

                desc_el = item.select_one(".event-description")
                if desc_el:
                    event["description"] = desc_el.get_text(separator=" ", strip=True)

                img = item.select_one(".event-thumbnail img")
                if img:
                    src = img.get("src") or img.get("data-src")
                    if src:
                        event["image_url"] = self.resolve_url(src, config.base_url)

                link = item.select_one(".event-content a")
                if link and link.get("href"):
                    event["detail_url"] = self.resolve_url(link["href"], config.base_url)

                if event.get("title"):
                    events_raw.append(event)

        logger.info(f"  Visit Škofja Loka: skupaj {len(events_raw)} dogodkov")
        return events_raw
