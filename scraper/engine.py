"""
Glavni scraping engine.
Bere YAML konfiguracije, izbere ustrezen parser in zbira dogodke iz virov.
Parserji so registrirani v scraper/parsers/ paketu.
"""

import os
import sys
import time
import hashlib
import logging
import re
import json
from datetime import datetime, date, timedelta
from urllib.parse import urljoin, urlparse, urlencode, parse_qs, urlunparse

import yaml
import requests
import cloudscraper
from bs4 import BeautifulSoup

# Dodaj parent dir v path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.models import (
    Session, Event, ScrapeLog, MediaOutlet, event_media, init_db, SourceHealth,
)
from scraper.dedup import compute_dedup_hash, is_duplicate, is_duplicate_fuzzy, DedupConfig
from scraper.published_checker import PublishedChecker
from scraper.categorizer import categorize_event
from scraper.image_fallback import find_fallback_image
from scraper.persistence import upsert_event, mark_stale_events
from scraper.retry import retry_with_backoff
from scraper.disabled_sources import is_source_disabled

# Registriraj vse parserje (import sproži @ParserRegistry.register)
from scraper.parsers import get_parser
import scraper.parsers.html_parser       # noqa: F401
import scraper.parsers.feed_parsers      # noqa: F401
import scraper.parsers.special_parsers   # noqa: F401

logger = logging.getLogger("scraper")


class SourceConfig:
    """Naloži in hrani konfiguracijo posameznega vira"""

    def __init__(self, yaml_path):
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        src = data["source"]
        self.id = src["id"]
        self.name = src["name"]
        self.base_url = src["base_url"]
        self.list_url = src["list_url"]
        self.region = src.get("region", "")
        self.parser_type = src.get("parser_type", "html")
        self.feed_url = src.get("feed_url", "")

        # Paginacija
        pag = src.get("pagination", {})
        self.pagination_type = pag.get("type", "query")
        self.pagination_param = pag.get("param", "page")
        self.pagination_start = pag.get("start", 1)
        self.max_pages = pag.get("max_pages", 5)

        # Selektorji
        self.list_selectors = src.get("list_selectors", {})
        self.detail_selectors = src.get("detail_selectors", {})
        self.json_fields = src.get("json_fields", {})

        # Nastavitve
        settings = src.get("settings", {})
        self.delay = settings.get("delay_between_requests", 2)
        self.timeout = settings.get("timeout", 30)
        self.encoding = settings.get("encoding", "utf-8")
        self.user_agent = settings.get("user_agent", "EventScraper/1.0")


class ScraperEngine:
    """
    Glavni engine za scraping dogodkov.
    Koordinira vire, parserje, deduplikacijo in shranjevanje.
    Parserji so ločeni v scraper/parsers/ paketu.
    """

    def __init__(self):
        self.config_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "config"
        )
        self.session = requests.Session()
        self.cloud_session = cloudscraper.create_scraper()
        self.published_checker = PublishedChecker()

    def load_sources(self):
        """Naloži vse YAML konfiguracije virov"""
        sources_dir = os.path.join(self.config_dir, "sources")
        sources = []
        for filename in os.listdir(sources_dir):
            if filename.endswith(".yaml") or filename.endswith(".yml"):
                path = os.path.join(sources_dir, filename)
                try:
                    sources.append(SourceConfig(path))
                    logger.info(f"Naložen vir: {filename}")
                except Exception as e:
                    logger.error(f"Napaka pri branju {filename}: {e}")
        return sources

    def load_media_config(self):
        """Naloži konfiguracijo medijev"""
        media_path = os.path.join(self.config_dir, "media.yaml")
        with open(media_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def fetch_page(self, url, config, use_cloudscraper=False):
        """Prenesi HTML stran z retry logiko."""
        headers = {"User-Agent": config.user_agent}
        http_session = self.cloud_session if use_cloudscraper else self.session
        max_retries = 2

        for attempt in range(max_retries + 1):
            try:
                resp = http_session.get(url, headers=headers, timeout=config.timeout)
                resp.encoding = config.encoding
                resp.raise_for_status()
                return resp.text
            except requests.RequestException as e:
                # Fallback na cloudscraper pri 403
                if not use_cloudscraper and "403" in str(e):
                    logger.info(f"  403 zaznana, poskušam s cloudscraper: {url}")
                    return self.fetch_page(url, config, use_cloudscraper=True)
                if attempt < max_retries:
                    wait = 2 ** attempt
                    logger.warning(f"  Retry {attempt+1}/{max_retries} za {url} (čakam {wait}s): {e}")
                    time.sleep(wait)
                else:
                    logger.error(f"Napaka pri prenosu {url}: {e}")
                    return None

    def get_paginated_urls(self, config):
        """Generiraj URL-je za vse strani paginacije"""
        urls = [config.list_url]
        for page_num in range(config.pagination_start + 1,
                              config.pagination_start + config.max_pages):
            parsed = urlparse(config.list_url)
            params = parse_qs(parsed.query)
            params[config.pagination_param] = [str(page_num)]
            new_query = urlencode(params, doseq=True)
            paginated_url = urlunparse(parsed._replace(query=new_query))
            urls.append(paginated_url)
        return urls

    def scrape_detail_page(self, url, config):
        """Poberi podrobnosti iz podstrani dogodka"""
        details = {}
        html = self.fetch_page(url, config)
        if not html:
            return details

        soup = BeautifulSoup(html, "lxml")
        ds = config.detail_selectors

        from scraper.parsers.base import BaseParser
        details["description"] = BaseParser.extract_text(soup, ds.get("description", ""))
        details["location"] = BaseParser.extract_text(soup, ds.get("location", ""))
        details["price"] = BaseParser.extract_text(soup, ds.get("price", ""))
        details["organizer"] = BaseParser.extract_text(soup, ds.get("organizer", ""))
        details["district"] = BaseParser.extract_text(soup, ds.get("district", ""))

        time_text = BaseParser.extract_text(soup, ds.get("time", ""))
        if time_text:
            t_start, t_end = BaseParser.parse_time(time_text)
            details["time_start"] = t_start
            details["time_end"] = t_end

        img_sel = ds.get("image", "")
        img_attr = ds.get("image_attr", "src")
        if img_sel:
            img_url = BaseParser.extract_attr(soup, img_sel, img_attr)
            if not img_url:
                img_url = BaseParser.extract_attr(soup, img_sel, "data-src")
            if img_url:
                details["image_url"] = BaseParser.resolve_url(img_url, config.base_url)

        return details

    def scrape_source(self, config, dedup_config=None, session_id=None):
        """Zaženi scraping za en vir z UPSERT logiko (Phase 1).

        Statusi v event_media in zgodovina v event_edits ostanejo nedotaknjeni.
        Dogodki, ki jih scraper ne najde, se označijo z is_active=False.
        """
        db = Session()
        log = ScrapeLog(source_id=config.id, status="running", session_id=session_id)
        db.add(log)
        db.commit()
        scrape_started_at = log.started_at

        all_events = []
        new_event_ids = []
        updated_event_ids = []
        # Disabled vir — preskoči
        if is_source_disabled(config.id):
            log.status = "skipped"
            log.error_message = "disabled in YAML config"
            log.finished_at = datetime.utcnow()
            db.commit()
            db.close()
            return {"found": 0, "new": 0, "updated": 0, "duplicates": 0,
                    "stale": 0, "new_ids": [], "skipped_reason": "disabled"}

        try:
            # Poišči ustrezen parser
            parser = get_parser(config.parser_type, source_id=config.id, fetcher=self)

            if parser is None:
                # Fallback na generični HTML parser
                from scraper.parsers.html_parser import HtmlParser
                parser = HtmlParser(fetcher=self)
                logger.warning(f"  Ni registriranega parserja za {config.parser_type}, uporabam html")

            # Ročni viri — preskočimo
            if config.parser_type == "manual":
                logger.info(f"  Ročni vir {config.name} - preskakujem avtomatski scraping")
                log.status = "skipped"
                log.events_found = 0
                log.events_new = 0
                log.finished_at = datetime.utcnow()
                db.commit()
                db.close()
                return {"found": 0, "new": 0, "updated": 0, "duplicates": 0,
                        "stale": 0, "new_ids": [], "updated_ids": [],
                        "skipped_reason": "manual_parser"}

            # Feed parserji sami pridobijo podatke
            if not parser.needs_html:
                all_events = parser.parse(config)
            else:
                # HTML parserji potrebujejo predhodni fetch
                urls = self.get_paginated_urls(config)
                logger.info(f"Scraping {config.name} ({len(urls)} strani)...")

                for i, url in enumerate(urls):
                    logger.info(f"  Stran {i+1}/{len(urls)}: {url}")
                    html = self.fetch_page(url, config)
                    if not html:
                        continue

                    events_raw = parser.parse(config, html=html)

                    if not events_raw:
                        logger.info(f"  Ni dogodkov na strani {i+1}, končujem paginacijo")
                        break

                    all_events.extend(events_raw)
                    time.sleep(config.delay)

            # Poberi podrobnosti za HTML parserje ki jih potrebujejo
            if not parser.skip_details:
                logger.info(f"  Pobiramo podrobnosti za {len(all_events)} dogodkov...")
                for event_data in all_events:
                    detail_url = event_data.get("detail_url")
                    if detail_url:
                        details = self.scrape_detail_page(detail_url, config)
                        for key, value in details.items():
                            if value and not event_data.get(key):
                                event_data[key] = value
                        time.sleep(config.delay)
            else:
                logger.info(f"  Preskakujem podstrani za {config.name}")

            # ============== UPSERT logika (Phase 1) ==============
            new_count = 0
            updated_count = 0
            dup_count = 0
            skip_count = 0

            for event_data in all_events:
                try:
                    decision, event = upsert_event(
                        db, event_data,
                        source_id=config.id,
                        region=config.region,
                        config=dedup_config,
                    )
                    if decision == "new":
                        new_count += 1
                        if event:
                            new_event_ids.append(event.id)
                    elif decision == "updated":
                        updated_count += 1
                        if event:
                            updated_event_ids.append(event.id)
                    elif decision == "duplicate":
                        dup_count += 1
                    else:  # skipped
                        skip_count += 1
                except Exception as ev_err:
                    # Napaka pri enem dogodku ne sme ustaviti vira
                    logger.warning(f"  Napaka pri dogodku '{event_data.get('title','')[:40]}': {ev_err}")
                    skip_count += 1
                    continue

            db.commit()

            # Mark-stale: aktivni dogodki iz tega vira, ki jih nismo ponovno videli
            stale_count = mark_stale_events(db, config.id, scrape_started_at)
            db.commit()

            # Posodobi log
            log.finished_at = datetime.utcnow()
            log.events_found = len(all_events)
            log.events_new = new_count
            log.events_updated = updated_count
            log.events_duplicate = dup_count
            log.events_marked_stale = stale_count
            log.status = "success"
            db.commit()

            # Posodobi SourceHealth
            self._update_source_health(
                db, config, success=True, events_found=len(all_events),
                duration_ms=int((datetime.utcnow() - scrape_started_at).total_seconds() * 1000),
            )
            db.commit()

            logger.info(
                f"  Končano: {len(all_events)} najdenih, "
                f"{new_count} novih, {updated_count} posodobljenih, "
                f"{dup_count} duplikatov, {stale_count} označenih kot neaktivni"
            )

        except Exception as e:
            log.status = "error"
            log.error_message = str(e)[:500]
            log.finished_at = datetime.utcnow()
            try:
                db.commit()
                self._update_source_health(db, config, success=False, error_msg=str(e))
                db.commit()
            except Exception:
                db.rollback()
            logger.error(f"  Napaka pri scrapingu {config.name}: {e}")
            raise
        finally:
            db.close()

        return {
            "found": len(all_events),
            "new": new_count,
            "updated": updated_count,
            "duplicates": dup_count,
            "stale": stale_count,
            "new_ids": new_event_ids,
            "updated_ids": updated_event_ids,
        }

    def _enrich_per_source(self, new_ids, source_id, progress=None):
        """Per-source parallel enrichment.

        Z 8 workerji: 30 dogodkov × ~8s / 8 = ~30 sekund.
        Časovna omejitev 90s (z varovalko).
        """
        if not new_ids:
            return
        try:
            from scraper.image_fallback import (
                fill_missing_descriptions, fill_missing_images,
            )
            db_e = Session()
            try:
                fill_missing_descriptions(
                    db_e, event_ids=new_ids, max_seconds=90, parallel_workers=8,
                )
            finally:
                db_e.close()
            db_e = Session()
            try:
                fill_missing_images(
                    db_e, event_ids=new_ids, max_seconds=90, parallel_workers=8,
                )
            finally:
                db_e.close()
        except Exception as e:
            logger.warning(f"  Per-source enrichment napaka za {source_id}: {e}")

    def _update_source_health(self, db, config, success: bool, events_found: int = 0,
                              duration_ms: int = 0, error_msg: str = None,
                              retry_count: int = 0):
        """Posodobi SourceHealth zapis za vir."""
        from datetime import datetime as _dt
        now = _dt.utcnow()
        sh = db.query(SourceHealth).get(config.id)
        if sh is None:
            sh = SourceHealth(
                source_id=config.id, source_name=config.name,
                parser_type=config.parser_type,
                feed_url=getattr(config, "feed_url", None),
                list_url=getattr(config, "list_url", None),
            )
            db.add(sh)

        sh.last_check = now
        sh.last_retry_count = retry_count
        if duration_ms:
            # Eksponentno povprečje (alfa=0.3)
            prev = sh.avg_duration_ms or 0
            sh.avg_duration_ms = int(0.7 * prev + 0.3 * duration_ms)

        if success:
            sh.last_success = now
            sh.last_events_found = events_found
            sh.success_count = (sh.success_count or 0) + 1
            sh.consecutive_errors = 0
            sh.consecutive_successes = (sh.consecutive_successes or 0) + 1
            if sh.consecutive_successes >= 3:
                sh.status = "healthy"
            else:
                sh.status = "degraded" if sh.consecutive_errors > 0 else "healthy"
        else:
            sh.last_error = now
            sh.last_error_msg = (error_msg or "")[:1000]
            sh.error_count = (sh.error_count or 0) + 1
            sh.consecutive_errors = (sh.consecutive_errors or 0) + 1
            sh.consecutive_successes = 0
            if sh.consecutive_errors >= 5:
                sh.status = "broken"
            else:
                sh.status = "degraded"

    # Aliasi za poenotenje regijskih nazivov
    REGION_ALIASES = {
        "pomurje": "pomurska",
        "murska-sobota": "pomurska",
        "lendava": "pomurska",
        "prlekija": "pomurska",
        "mol": "osrednjeslovenska",
        # Ljubljana ostaja kot občinski naziv (LjubljanaInfo ga uporablja kot primary_region)
        # ampak osrednjeslovenska in mol sta sinonim
        "jugovzhodna": "dolenjska",
        "jugovzhodna-slovenija": "dolenjska",
    }

    @classmethod
    def normalize_region(cls, region):
        """Vrni kanonsko obliko imena regije."""
        if not region:
            return region
        return cls.REGION_ALIASES.get(region.lower().strip(), region.lower().strip())

    def get_sources_for_media(self, media_id):
        """Vrni samo tiste vire, ki spadajo v primary_regions ali secondary_regions
        izbranega medija. Dogodki iz teh virov se prikazujejo na tem mediju."""
        if not media_id:
            return self.load_sources()

        media_config = self.load_media_config()
        media = next((m for m in media_config.get("media", []) if m["id"] == media_id), None)
        if not media:
            return []

        target_regions = set()
        for r in (media.get("primary_regions") or []) + (media.get("secondary_regions") or []):
            target_regions.add(self.normalize_region(r))

        sources = self.load_sources()
        return [
            s for s in sources
            if self.normalize_region(s.region) in target_regions
        ]

    def assign_events_to_media(self):
        """
        Centralizirano razvrščanje dogodkov na 7 portalov.
        Dogodki se dodelijo glede na primary_regions in secondary_regions.
        """
        db = Session()
        try:
            media_config = self.load_media_config()

            # Ustvari/posodobi medije v bazi
            for m in media_config.get("media", []):
                all_regions = m.get("primary_regions", []) + m.get("secondary_regions", [])
                media = db.query(MediaOutlet).get(m["id"])
                if not media:
                    media = MediaOutlet(
                        id=m["id"],
                        name=m["name"],
                        regions=json.dumps(all_regions)
                    )
                    db.add(media)
                else:
                    media.regions = json.dumps(all_regions)
            db.commit()

            # Naloži vire za mapiranje source_id → region
            sources = self.load_sources()
            source_region_map = {s.id: s.region for s in sources}

            # Dodeli nove dogodke
            cutoff = date.today()
            future_events = db.query(Event).filter(Event.date_start >= cutoff).all()

            for m in media_config.get("media", []):
                primary = {self.normalize_region(r) for r in m.get("primary_regions", [])}
                secondary = {self.normalize_region(r) for r in m.get("secondary_regions", [])}
                media = db.query(MediaOutlet).get(m["id"])

                assigned = 0
                for event in future_events:
                    if media in event.media_outlets:
                        continue

                    event_region = self.normalize_region(
                        event.region or source_region_map.get(event.source_id, "")
                    )

                    if event_region in primary:
                        event.media_outlets.append(media)
                        assigned += 1
                    elif event_region in secondary:
                        # Za nacionalne vire dodeli samo če je lokacija
                        # relevantna za ta portal (ni iz druge regije)
                        if event.source_id in ("kulturnik-rss-slovenija", "kultura-media", "mynight"):
                            if self._is_location_relevant(event, primary):
                                event.media_outlets.append(media)
                                assigned += 1

                if assigned:
                    logger.info(f"  Dodeljenih {assigned} dogodkov za {m['name']}")

            db.commit()
        finally:
            db.close()

    # Lokacije ki spadajo v posamezne regije — za filtriranje nacionalnih virov
    LOCATION_REGION_MAP = {
        # Pomurska
        "murska sobota": {"pomurska", "pomurje", "murska-sobota"},
        "lendava": {"pomurska", "pomurje", "lendava"},
        "ljutomer": {"pomurska", "pomurje", "prlekija"},
        "gornja radgona": {"pomurska", "pomurje"},
        # Podravska
        "maribor": {"maribor", "podravska"},
        "ptuj": {"ptuj", "podravska"},
        "ormož": {"ormoz", "podravska"},
        # Ljubljana
        "ljubljana": {"ljubljana", "osrednjeslovenska", "mol"},
        # Gorenjska
        "kranj": {"gorenjska"},
        "bled": {"gorenjska"},
        "bohinj": {"gorenjska"},
        "škofja loka": {"gorenjska"},
        "jesenice": {"gorenjska"},
        # Dolenjska
        "novo mesto": {"dolenjska", "jugovzhodna"},
        "krško": {"dolenjska", "posavje"},
        "brežice": {"dolenjska", "posavje"},
        "sevnica": {"dolenjska", "posavje"},
        # Celje/Savinjska (ni naš portal, ne dodeljevat)
        "celje": {"savinjska"},
        "velenje": {"savinjska"},
        "trbovlje": {"zasavska"},
        # Primorska
        "koper": {"primorska"},
        "piran": {"primorska"},
        "nova gorica": {"primorska", "goriška"},
        "izola": {"primorska"},
        "tolmin": {"primorska", "goriška"},
    }

    def _is_location_relevant(self, event, portal_regions):
        """
        Preveri ali je lokacija dogodka relevantna za portal.
        Za nacionalne vire (kulturnik-rss-slovenija) preveri ali lokacija
        spada v regije portala. Če lokacije ni mogoče določiti, preskoči.
        """
        location = (event.location or "").lower()
        if not location:
            return False  # Brez lokacije ne dodeljevaj nacionalnih

        # Preveri ali lokacija vsebuje ime kraja ki ga poznamo
        for place, place_regions in self.LOCATION_REGION_MAP.items():
            if place in location:
                # Kraj najden — preveri ali spada v regije portala
                return bool(portal_regions & place_regions)

        # Lokacija ni v naši mapi — morda je festival ali kaj posebnega
        # Dodeli samo če je v naslovu/opisu omemba regije
        title_loc = (event.title or "").lower() + " " + location
        for region in portal_regions:
            if region in title_loc:
                return True

        return False

    def run_all(self, progress=None, media_id=None, dedup_config=None,
                retry_attempts=2, retry_base_delay=2.0, cancel_event=None,
                session_id=None):
        """Zaženi scraping virov (PHASE 1: persistent storage).

        - NE briše več baze. Uporablja UPSERT (update obstoječi / insert nov).
        - Dogodki, ki jih scraper več ne najde, se označijo z is_active=False.
        - Statusi v event_media in zgodovina v event_edits ostanejo.
        - Per-source retry z exponential backoff (privzeto 2 dodatna poskusa).
        - Napaka enega vira NE ustavi celotnega procesa.

        `media_id`: scrapaš samo vire iz regij tega medija (sicer vse).
        `dedup_config`: DedupConfig za nastavitev thresholdov.
        `progress`: dict za live UI posodobitve.
        """
        init_db()

        if progress is None:
            progress = {}

        # Določi vire za scrape
        if media_id:
            sources = self.get_sources_for_media(media_id)
            source_ids = {s.id for s in sources}
            scope_label = f"medij '{media_id}' ({len(sources)} virov)"
        else:
            sources = self.load_sources()
            source_ids = None  # pomeni VSE
            scope_label = f"vsi viri ({len(sources)})"

        # 0. PHASE 1: NE BRIŠEMO več. Samo počistimo staro ScrapeLog zgodovino
        # (obdrži zadnjih 200 zapisov za diagnostiko).
        progress.update({"phase": "preparing", "percent": 0, "scope": scope_label})
        logger.info(f"Pripravljam scrape ({scope_label}) — persistent mode...")
        db_clear = Session()
        try:
            old_logs = db_clear.query(ScrapeLog).order_by(
                ScrapeLog.started_at.desc()
            ).offset(200).all()
            for l in old_logs:
                db_clear.delete(l)
            db_clear.commit()
        except Exception as e:
            db_clear.rollback()
            logger.warning(f"Cleanup logs failed: {e}")
        finally:
            db_clear.close()

        # 1. Preveri že objavljene
        progress.update({"phase": "checking_published", "percent": 2})
        logger.info("Preverjam že objavljene dogodke na portalih...")
        try:
            self.published_checker.check_all_portals()
        except Exception as e:
            logger.warning(f"Napaka pri preverjanju portalov: {e}")

        # 2. Scrape virov (sources že določeni zgoraj)
        total = len(sources)
        results = {}
        all_new_ids = []  # ID-ji novih dogodkov samo iz tega zagona
        progress.update({
            "phase": "scraping",
            "total_sources": total,
            "current_index": 0,
            "percent": 0,
        })

        for i, source in enumerate(sources, 1):
            # Preverimo cancel_event pred vsakim virom
            if cancel_event is not None and cancel_event.is_set():
                logger.warning(f"  Scrape PREKINJEN po viru {i-1}/{total}.")
                progress.update({"phase": "cancelled", "percent": int(2 + 73 * (i - 1) / max(total, 1))})
                results["_cancelled"] = True
                results["_cancelled_at_index"] = i - 1
                return results

            progress.update({
                "current_source": source.name,
                "current_source_id": source.id,
                "current_index": i,
                "percent": int(2 + 73 * (i - 1) / max(total, 1)),  # 2-75% za scrape fazo
            })
            try:
                result, attempts_used = retry_with_backoff(
                    lambda s=source: self.scrape_source(s, dedup_config=dedup_config, session_id=session_id),
                    max_attempts=retry_attempts + 1,
                    base_delay=retry_base_delay,
                    max_delay=15.0,
                )
                if attempts_used > 1:
                    result["retry_attempts"] = attempts_used - 1
                results[source.id] = result
                if isinstance(result, dict) and result.get("new_ids"):
                    all_new_ids.extend(result["new_ids"])
                    # PER-SOURCE ENRICHMENT — takoj obogati nove dogodke iz tega vira
                    # (manjši batch = bolj zanesljivo, ne nakopiči se)
                    self._enrich_per_source(result["new_ids"], source.id, progress)
            except Exception as e:
                # Po vseh retry-jih še vedno napaka — beleži in nadaljuj
                results[source.id] = {"error": str(e), "retry_attempts": retry_attempts}
                logger.error(f"  KONČNA napaka {source.id} po {retry_attempts + 1} poskusih: {e}")

        # 3. Per-source enrichment je že potekal med scrape-om (takoj po vsakem viru).
        # Tu samo še preverimo če so kateri dogodki ostali brez opisa/slike — npr.
        # zaradi timeout-ov — in jih obogatimo v skupnem batch-u.
        progress.update({
            "phase": "enrichment", "current_source": None, "percent": 88,
            "new_event_count": len(all_new_ids),
        })
        try:
            from scraper.image_fallback import fill_missing_descriptions, fill_missing_images
            db_e = Session()
            try:
                d_total, d_filled = fill_missing_descriptions(
                    db_e, event_ids=all_new_ids,
                    progress=progress, max_seconds=120,
                    percent_range=(88, 92),
                )
                logger.info(f"Enrichment retry opisi: {d_filled}/{d_total}")
            finally:
                db_e.close()
            db_e = Session()
            try:
                i_total, i_real, i_fb = fill_missing_images(
                    db_e, event_ids=all_new_ids,
                    progress=progress, max_seconds=120,
                    percent_range=(92, 95),
                )
                logger.info(f"Enrichment retry slike: {i_real} + {i_fb} simbolnih od {i_total}")
            finally:
                db_e.close()
        except Exception as e:
            logger.warning(f"Auto-enrichment retry napaka: {e}")

        # 4. Dodeli medijem in označi objavljene
        progress.update({"phase": "assigning", "percent": 96})
        self.assign_events_to_media()
        self._mark_published_events()

        # 5. Background continuation: če so še dogodki brez slike/opisa,
        # zaženi ozadnji enrichment (ne čakamo na konec).
        try:
            self._spawn_background_enrichment_if_needed()
        except Exception as e:
            logger.warning(f"Background enrichment spawn napaka: {e}")

        progress.update({"phase": "done", "percent": 100})
        return results

    def _spawn_background_enrichment_if_needed(self, threshold=10):
        """Če je v bazi >= threshold dogodkov brez opisa ali slike,
        sproži ozadnji daemon thread, ki počasi obdela vse v batch-ih.
        Threshold prepreči nepotrebno ozadno delo za majhne primanjkljaje."""
        import threading
        from sqlalchemy import or_ as _or
        from datetime import date as _d

        db = Session()
        try:
            missing_desc = db.query(Event).filter(
                Event.date_start >= _d.today(),
                Event.is_active == True,  # noqa
                _or(Event.description == None, Event.description == ""),  # noqa
                Event.source_url != None,  # noqa
            ).count()
            missing_img = db.query(Event).filter(
                Event.date_start >= _d.today(),
                Event.is_active == True,  # noqa
                _or(Event.image_url == None, Event.image_url == ""),  # noqa
                Event.source_url != None,  # noqa
            ).count()
        finally:
            db.close()

        if missing_desc < threshold and missing_img < threshold:
            return

        logger.info(f"Spawn background enrichment: {missing_desc} brez opisa, "
                    f"{missing_img} brez slike.")

        def _bg():
            from scraper.image_fallback import (
                fill_missing_descriptions, fill_missing_images,
            )
            try:
                # Več manjših batch-ov da ne blokira nikoli za dolgo
                for batch_no in range(5):  # do 5 batch-ov × 100 = 500 dogodkov
                    db_b = Session()
                    try:
                        d_total, _ = fill_missing_descriptions(
                            db_b, limit=100, max_seconds=180, parallel_workers=8,
                        )
                    finally:
                        db_b.close()
                    db_b = Session()
                    try:
                        i_total, _, _ = fill_missing_images(
                            db_b, limit=100, max_seconds=180, parallel_workers=8,
                        )
                    finally:
                        db_b.close()
                    if d_total == 0 and i_total == 0:
                        break  # nič več za delo
            except Exception as e:
                logger.warning(f"Background enrichment napaka: {e}")

        threading.Thread(target=_bg, daemon=True, name="bg_enrichment").start()

    def _mark_published_events(self):
        """Po dodelitvi preveri ali so kateri že objavljeni na portalih.
        Resetira cache pred uporabo, da dobi sveže podatke iz portalov."""
        try:
            self.published_checker.reset_cache()
        except Exception:
            pass
        db = Session()
        try:
            media_config = self.load_media_config()
            marked = 0

            for m in media_config.get("media", []):
                media_id = m["id"]
                try:
                    published = self.published_checker.fetch_published_events(media_id)
                except Exception as fe:
                    logger.warning(f"  Published fetch napaka za {media_id}: {fe}")
                    continue
                if not published:
                    logger.info(f"  {media_id}: 0 že objavljenih (preskačem mark-published)")
                    continue
                logger.info(f"  {media_id}: {len(published)} že objavljenih, preverjam ujemanje...")

                from sqlalchemy import and_
                new_events = db.execute(
                    event_media.select().where(
                        and_(
                            event_media.c.media_id == media_id,
                            event_media.c.status == "new"
                        )
                    )
                ).fetchall()

                for row in new_events:
                    event = db.query(Event).get(row.event_id)
                    if not event:
                        continue

                    from scraper.dedup import check_against_published
                    if check_against_published(event.title, event.date_start, published):
                        db.execute(
                            event_media.update()
                            .where(event_media.c.event_id == event.id)
                            .where(event_media.c.media_id == media_id)
                            .values(status="published")
                        )
                        marked += 1
                        logger.info(f"  Že objavljen na {media_id}: {event.title[:50]}")

            db.commit()
            if marked:
                logger.info(f"  Skupaj {marked} dogodkov označenih kot že objavljeni")
        except Exception as e:
            logger.warning(f"Napaka pri označevanju objavljenih: {e}")
        finally:
            db.close()


def main():
    """CLI vstopna točka"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    engine = ScraperEngine()

    if len(sys.argv) > 1 and sys.argv[1] == "--source":
        source_id = sys.argv[2]
        sources = engine.load_sources()
        source = next((s for s in sources if s.id == source_id), None)
        if source:
            result = engine.scrape_source(source)
            print(f"Rezultat: {result}")
        else:
            print(f"Vir '{source_id}' ni najden")
    else:
        results = engine.run_all()
        print("\n=== REZULTATI ===")
        for source_id, result in results.items():
            print(f"  {source_id}: {result}")


if __name__ == "__main__":
    main()
