"""
Bootstrap MediaOutlet zapisov iz config/media.yaml ob startupu.
Sicer dropdown "Medij" v dashboardu ostane prazen, dokler ne teče prvi scrape.
"""

import json
import logging
import os

import yaml

from database.models import MediaOutlet, get_db

logger = logging.getLogger(__name__)


def bootstrap_media_outlets():
    """Sinhroniziraj media.yaml → MediaOutlet tabela.
    Idempotenten: lahko se kliče ob vsakem startupu."""
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "config", "media.yaml",
    )
    if not os.path.exists(config_path):
        logger.warning(f"media.yaml ne obstaja: {config_path}")
        return 0

    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    media_list = cfg.get("media", [])
    created_or_updated = 0

    with get_db() as db:
        for m in media_list:
            mid = m.get("id")
            if not mid:
                continue
            all_regions = (m.get("primary_regions") or []) + (m.get("secondary_regions") or [])
            outlet = db.query(MediaOutlet).get(mid)
            if outlet is None:
                outlet = MediaOutlet(
                    id=mid,
                    name=m.get("name", mid),
                    url=m.get("url"),
                    regions=json.dumps(all_regions, ensure_ascii=False),
                )
                db.add(outlet)
                created_or_updated += 1
            else:
                outlet.name = m.get("name", outlet.name)
                outlet.url = m.get("url", outlet.url)
                outlet.regions = json.dumps(all_regions, ensure_ascii=False)
                created_or_updated += 1

    logger.info(f"Bootstrap media outlets: {created_or_updated} sinhroniziranih.")
    return created_or_updated
