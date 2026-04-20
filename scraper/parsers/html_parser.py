"""
Generični HTML parser za sezname dogodkov.
Uporablja CSS selektorje iz YAML konfiguracije.
"""

import logging
from bs4 import BeautifulSoup

from scraper.parsers.base import BaseParser
from scraper.parsers.registry import ParserRegistry

logger = logging.getLogger("scraper")


@ParserRegistry.register("html")
class HtmlParser(BaseParser):
    """Generični HTML parser — bere seznam dogodkov iz HTML strani."""

    @property
    def needs_html(self):
        return True

    @property
    def skip_details(self):
        return False

    def parse(self, config, html=None):
        """Razčleni seznam dogodkov iz HTML z uporabo CSS selektorjev."""
        if not html:
            return []

        soup = BeautifulSoup(html, "lxml")
        events_raw = []

        card_selector = config.list_selectors.get("event_card", "")
        cards = soup.select(card_selector) if card_selector else []
        logger.info(f"  Najdenih kartic: {len(cards)}")

        for card in cards:
            event = {}

            # Naslov
            event["title"] = self.extract_text(card, config.list_selectors.get("title", ""))

            # Datum
            date_text = self.extract_text(card, config.list_selectors.get("date", ""))
            event["date_text"] = date_text
            event["date_start"], event["date_end"] = self.parse_date(date_text)

            # Ura
            time_start, time_end = self.parse_time(date_text)
            event["time_start"] = time_start
            event["time_end"] = time_end

            # Slika
            img_attr = config.list_selectors.get("image_attr", "src")
            img_sel = config.list_selectors.get("image", "img")
            img_url = self.extract_attr(card, img_sel, img_attr)
            if not img_url:
                img_url = self.extract_attr(card, img_sel, "data-src")
            event["image_url"] = self.resolve_url(img_url, config.base_url)

            # Opis
            desc_sel = config.list_selectors.get("description", "")
            if desc_sel:
                event["description"] = self.extract_text(card, desc_sel)

            # Cena
            price_sel = config.list_selectors.get("price", "")
            if price_sel:
                event["price"] = self.extract_text(card, price_sel)

            # Kategorije
            cat_sel = config.list_selectors.get("categories", "")
            if cat_sel:
                cat_els = card.select(cat_sel)
                if cat_els:
                    event["categories"] = ", ".join(
                        el.get_text(strip=True) for el in cat_els
                    )

            # Povezava do podstrani
            link_sel = config.list_selectors.get("detail_link", "")
            link_attr = config.list_selectors.get("detail_link_attr", "href")
            if link_sel:
                detail_url = self.extract_attr(card, link_sel, link_attr)
            else:
                detail_url = card.get("href") if card.name == "a" else None
            event["detail_url"] = self.resolve_url(detail_url, config.base_url)

            if event["title"]:
                events_raw.append(event)

        return events_raw
