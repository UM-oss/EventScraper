#!/usr/bin/env python3
"""
Sinhronizacija že-objavljenih dogodkov iz portalov.

Namen: GitHub Actions ima drug IP range kot Render, zato Cloudflare na
portalih ne blokira. Ta script teče enkrat dnevno (ali ročno), fetcha
koledarje vseh portalov in označi ujemajoče se dogodke v Render bazi
kot status='published'.

ENV:
  EVENT_SCRAPER_DATABASE_URL  — PostgreSQL URL (iz Render)
  GH_LOG_LEVEL               — INFO / DEBUG (default INFO)
"""

import os
import sys
import logging
from datetime import datetime
from sqlalchemy import and_

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Naloži env iz .env če obstaja
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(
    level=os.environ.get("GH_LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("sync_published")

from database.models import get_db, Event, event_media, EventEdit
from scraper.published_checker import PublishedChecker, PORTAL_CALENDARS
from scraper.dedup import check_against_published


def main():
    logger.info("=" * 60)
    logger.info(f"SYNC PUBLISHED — {len(PORTAL_CALENDARS)} portalov")
    logger.info("=" * 60)

    started = datetime.utcnow()
    checker = PublishedChecker(max_pages=10)

    total_marked = 0
    total_checked = 0
    portal_stats = {}

    for media_id in PORTAL_CALENDARS:
        try:
            published = checker.fetch_published_events(media_id)
        except Exception as e:
            logger.warning(f"  {media_id}: fetch failed: {e}")
            portal_stats[media_id] = {"error": str(e), "events_on_portal": 0, "marked": 0}
            continue

        portal_stats[media_id] = {"events_on_portal": len(published), "marked": 0, "checked": 0}

        if not published:
            logger.info(f"  {media_id}: 0 dogodkov na portalu")
            continue

        logger.info(f"  {media_id}: {len(published)} dogodkov na portalu")

        with get_db() as db:
            rows = db.execute(
                event_media.select().where(and_(
                    event_media.c.media_id == media_id,
                    event_media.c.status == "new",
                ))
            ).fetchall()

            for row in rows:
                ev = db.query(Event).get(row.event_id)
                if not ev or not ev.date_start:
                    continue
                portal_stats[media_id]["checked"] += 1
                total_checked += 1

                if check_against_published(ev.title, ev.date_start, published):
                    db.execute(
                        event_media.update().where(and_(
                            event_media.c.event_id == ev.id,
                            event_media.c.media_id == media_id,
                        )).values(
                            status="published",
                            published_at=datetime.utcnow(),
                            processed_at=datetime.utcnow(),
                        )
                    )
                    db.add(EventEdit(
                        event_id=ev.id,
                        field_name=f"em_status:{media_id}",
                        old_value="new", new_value="published",
                        source="github-actions-sync",
                        user_id=None,
                    ))
                    portal_stats[media_id]["marked"] += 1
                    total_marked += 1
                    logger.info(f"    ✓ Označen: {ev.title[:60]}")

    duration = int((datetime.utcnow() - started).total_seconds())

    logger.info("=" * 60)
    logger.info(f"REZULTATI ({duration}s):")
    logger.info(f"  Skupaj preverjenih: {total_checked}")
    logger.info(f"  Skupaj označenih kot 'published': {total_marked}")
    for mid, stats in portal_stats.items():
        if "error" in stats:
            logger.info(f"  {mid}: ERROR — {stats['error']}")
        else:
            logger.info(f"  {mid}: {stats['events_on_portal']} na portalu, "
                        f"{stats['checked']} preverjenih, {stats['marked']} označenih")
    logger.info("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
