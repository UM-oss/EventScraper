#!/usr/bin/env python3
"""
Migracija iz pre-Phase 1 SQLite baze (events.db.backup-pre-phase1) v
trenutno bazo z novimi stolpci.

Uporaba:
  venv/bin/python scripts/migrate_legacy_sqlite.py \\
      --source data/events.db.backup-pre-phase1 \\
      [--dry-run]

Kaj migrira:
- Eventi (po dedup_hash + (source_id, source_event_id) ujemanju)
- Statusi v event_media (approved, skipped, ...)
- Editor_notes, featured

NE migrira:
- ScrapeLog zgodovine (ne potrebujemo)
- DrupalPushLog (Drupal je out of scope)
- SourceHealth (sčasoma se ponovno zgradi)

Pristop "merge":
- Če dogodek z istim (source_id, source_event_id) že obstaja → posodobi event_media
- Če dogodek ne obstaja → ne ustvarimo (bomo ga naslednji scrape)
- Pri konfliktu statusa: legacy zmaga (uporabnikove odločitve)
"""

import argparse
import sqlite3
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.models import get_db, Event, event_media, EventEdit
from sqlalchemy import and_


def migrate(source_db_path: str, dry_run: bool = False):
    if not os.path.exists(source_db_path):
        print(f"FATAL: Source DB ne obstaja: {source_db_path}")
        return 1

    print(f"Source: {source_db_path}")
    print(f"Dry run: {dry_run}")

    legacy = sqlite3.connect(source_db_path)
    legacy.row_factory = sqlite3.Row

    # 1. Beri vse legacy event_media zapise z ne-default statusom
    legacy_em = legacy.execute("""
        SELECT em.event_id, em.media_id, em.status, em.priority,
               em.featured, em.editor_notes,
               em.approved_at, em.processed_at,
               e.source_id, e.source_event_id, e.title, e.date_start
        FROM event_media em
        JOIN events e ON em.event_id = e.id
        WHERE em.status NOT IN ('new', 'archived')
    """).fetchall()

    print(f"Najdenih {len(legacy_em)} legacy event_media zapisov z ne-default statusom.")

    matched = 0
    unmatched = 0
    updated = 0

    with get_db() as db:
        for row in legacy_em:
            # Najdi novi event po (source_id, source_event_id) ALI po (title, date_start)
            new_event = None
            if row["source_event_id"]:
                new_event = db.query(Event).filter(
                    Event.source_id == row["source_id"],
                    Event.source_event_id == row["source_event_id"],
                ).first()

            if not new_event and row["date_start"]:
                # Fallback: po naslovu + datumu
                from datetime import date as _d
                try:
                    d = _d.fromisoformat(row["date_start"]) if isinstance(row["date_start"], str) else row["date_start"]
                except Exception:
                    d = None
                if d:
                    new_event = db.query(Event).filter(
                        Event.title == row["title"],
                        Event.date_start == d,
                    ).first()

            if not new_event:
                unmatched += 1
                continue

            matched += 1

            if dry_run:
                print(f"  WOULD UPDATE: {row['title'][:50]} → {row['media_id']} = {row['status']}")
                continue

            # Posodobi event_media
            existing = db.execute(
                event_media.select().where(and_(
                    event_media.c.event_id == new_event.id,
                    event_media.c.media_id == row["media_id"],
                ))
            ).fetchone()

            update_values = {
                "status": row["status"],
                "priority": row["priority"] or 0,
                "featured": bool(row["featured"]),
                "editor_notes": row["editor_notes"],
                "approved_at": row["approved_at"],
                "processed_at": row["processed_at"],
            }

            if existing:
                db.execute(
                    event_media.update().where(and_(
                        event_media.c.event_id == new_event.id,
                        event_media.c.media_id == row["media_id"],
                    )).values(**update_values)
                )
            else:
                db.execute(event_media.insert().values(
                    event_id=new_event.id,
                    media_id=row["media_id"],
                    **update_values,
                ))

            # Audit
            db.add(EventEdit(
                event_id=new_event.id,
                field_name=f"em_status:{row['media_id']}",
                old_value="new",
                new_value=row["status"],
                source="import",
                user_id=None,
            ))
            updated += 1

    legacy.close()

    print(f"\n=== POVZETEK ===")
    print(f"  Najdenih legacy zapisov: {len(legacy_em)}")
    print(f"  Ujetih z novim Event: {matched}")
    print(f"  NEUjetih: {unmatched}")
    print(f"  Dejansko posodobljenih: {updated}")
    if dry_run:
        print(f"  (DRY RUN — sprememb ni)")
    return 0


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", required=True, help="Path do legacy SQLite baze")
    p.add_argument("--dry-run", action="store_true", help="Samo poročaj, ne spreminjaj")
    args = p.parse_args()
    sys.exit(migrate(args.source, args.dry_run))


if __name__ == "__main__":
    main()
