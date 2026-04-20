#!/usr/bin/env python3
"""
Dnevni scrape — uporablja se kot Render Cron Job (vsak dan ob 6:00).

Sproži ScraperEngine.run_all() in zaključi proces. Brez Flask UI-ja, brez thread-ov.
Vsi rezultati so v DB (event_media, scrape_logs).
"""

import os
import sys
import time
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Naloži env iz .env če obstaja (lokalni test)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from scraper.observability import setup_logging
setup_logging()

from scraper.engine import ScraperEngine

logger = logging.getLogger("daily_scrape")


def main():
    days_ahead = int(os.environ.get("EVENT_SCRAPER_SCHEDULE_DAYS", "30"))
    media_id = os.environ.get("DAILY_SCRAPE_MEDIA") or None  # opcijsko: en medij

    logger.info("=" * 60)
    logger.info(f"DNEVNI SCRAPE — look-ahead {days_ahead} dni" +
                (f" (medij: {media_id})" if media_id else " (vsi viri)"))
    logger.info("=" * 60)

    started = time.time()
    progress = {"phase": "starting", "percent": 0}
    engine = ScraperEngine()
    results = engine.run_all(progress=progress, media_id=media_id)

    duration = int(time.time() - started)
    total_new = sum(r.get("new", 0) for r in results.values()
                    if isinstance(r, dict) and "error" not in r)
    total_updated = sum(r.get("updated", 0) for r in results.values()
                        if isinstance(r, dict) and "error" not in r)
    total_stale = sum(r.get("stale", 0) for r in results.values()
                      if isinstance(r, dict) and "error" not in r)
    errors = {sid: r["error"] for sid, r in results.items()
              if isinstance(r, dict) and "error" in r}

    logger.info("=" * 60)
    logger.info(f"KONČANO v {duration}s")
    logger.info(f"  novih: {total_new}")
    logger.info(f"  posodobljenih: {total_updated}")
    logger.info(f"  označenih kot neaktivni: {total_stale}")
    logger.info(f"  napake: {len(errors)} ({list(errors.keys())[:5]})")
    logger.info("=" * 60)

    # Webhook notifikacija (če nastavljen)
    try:
        from scraper.notifications import notify_scrape_complete
        notify_scrape_complete({
            "total_new": total_new,
            "total_updated": total_updated,
            "total_stale": total_stale,
            "sources_ok": len(results) - len(errors),
            "sources_err": len(errors),
            "duration_s": duration,
        })
    except Exception as e:
        logger.warning(f"Webhook failed: {e}")

    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
