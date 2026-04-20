"""
Strukturirano logiranje + osnovne metrike.

Logging format je JSON-friendly v produkciji (LOG_JSON=1) in human-readable
v razvoju.
"""

import os
import sys
import json
import logging
from datetime import datetime


class JsonFormatter(logging.Formatter):
    """Strukturirano JSON logiranje za produkcijo."""

    def format(self, record):
        out = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            out["exc"] = self.formatException(record.exc_info)
        # Dodaj custom fields
        for key in ("source_id", "event_id", "user_id", "duration_ms",
                    "events_found", "events_new", "retry_count"):
            v = getattr(record, key, None)
            if v is not None:
                out[key] = v
        return json.dumps(out, ensure_ascii=False)


class HumanFormatter(logging.Formatter):
    def __init__(self):
        super().__init__(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        )


def setup_logging():
    """Pokliče se enkrat ob startupu."""
    use_json = os.environ.get("LOG_JSON", "0").lower() in ("1", "true")
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter() if use_json else HumanFormatter())

    root = logging.getLogger()
    root.setLevel(log_level)
    # Počisti obstoječe handler-je
    for h in list(root.handlers):
        root.removeHandler(h)
    root.addHandler(handler)

    # Naredi eksplicitno tišino za nekaj noisy modulov
    logging.getLogger("urllib3").setLevel("WARNING")
    logging.getLogger("requests").setLevel("WARNING")
    logging.getLogger("apscheduler").setLevel("INFO")


# =====================================================================
# SISTEMSKE METRIKE (za /api/health)
# =====================================================================

def collect_system_metrics():
    """Vrne dict s ključnimi metrikami sistema (za health endpoint)."""
    from sqlalchemy import func
    from datetime import date, timedelta
    from database.models import (
        get_db, Event, ScrapeLog, SourceHealth, DedupDecision,
    )

    metrics = {}
    with get_db() as db:
        today = date.today()
        # Eventi
        metrics["events_total"] = db.query(Event).count()
        metrics["events_active"] = db.query(Event).filter(Event.is_active == True).count()  # noqa
        metrics["events_inactive"] = metrics["events_total"] - metrics["events_active"]
        metrics["events_future"] = db.query(Event).filter(
            Event.is_active == True, Event.date_start >= today  # noqa
        ).count()

        # Scrape logi (zadnjih 24h)
        cutoff_24h = datetime.utcnow() - timedelta(hours=24)
        recent = db.query(ScrapeLog).filter(ScrapeLog.started_at >= cutoff_24h).all()
        metrics["scrape_runs_24h"] = len(recent)
        metrics["scrape_success_24h"] = sum(1 for r in recent if r.status == "success")
        metrics["scrape_error_24h"] = sum(1 for r in recent if r.status == "error")
        metrics["events_new_24h"] = sum(r.events_new or 0 for r in recent)
        metrics["events_updated_24h"] = sum(r.events_updated or 0 for r in recent)

        # Source health
        broken_sources = db.query(SourceHealth).filter(
            SourceHealth.status == "broken"
        ).all()
        metrics["sources_broken"] = len(broken_sources)
        metrics["sources_broken_ids"] = [s.source_id for s in broken_sources]
        metrics["sources_degraded"] = db.query(SourceHealth).filter(
            SourceHealth.status == "degraded"
        ).count()

        # Dedup decisions (zadnjih 24h)
        metrics["dedup_decisions_24h"] = db.query(DedupDecision).filter(
            DedupDecision.created_at >= cutoff_24h
        ).count()

    return metrics
