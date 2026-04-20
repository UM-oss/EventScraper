"""
APScheduler integracija — periodično scrapanje.

Vključitev preko EVENT_SCRAPER_SCHEDULER=1 (privzeto vključeno v Phase 2,
da uporabnik dobi sveže dogodke vsako jutro).

Konfiguracija prek env spremenljivk:
  EVENT_SCRAPER_SCHEDULER         (0/1, default 1)
  EVENT_SCRAPER_SCHEDULE_MODE     "daily" | "interval" (default "daily")
  EVENT_SCRAPER_SCHEDULE_HOUR     ura za daily mode (default 6)
  EVENT_SCRAPER_SCHEDULE_MINUTE   minuta za daily mode (default 0)
  EVENT_SCRAPER_SCHEDULE_INTERVAL minute za interval mode (default 60)
  EVENT_SCRAPER_SCHEDULE_DAYS     look-ahead dni (default 30)
  EVENT_SCRAPER_SCHEDULE_AT_START 1 = poženi enkrat ob startupu (default 0)
"""

import os
import logging
import threading

logger = logging.getLogger("scheduler")

_scheduler = None
_scrape_runner = None  # callback iz app.py


def is_enabled() -> bool:
    # Privzeto VKLJUČENO v Phase 2 (avtomatski dnevni scrape).
    return os.environ.get("EVENT_SCRAPER_SCHEDULER", "1").lower() in ("1", "true", "yes")


def init_scheduler(scrape_runner_callback):
    """Pokliče se ob startupu Flask-a (v run_dashboard.py).

    `scrape_runner_callback`: funkcija ki sproži scrape (npr. _run_scrape_task).
    """
    global _scheduler, _scrape_runner

    if not is_enabled():
        logger.info("Scheduler IZKLOPLJEN (EVENT_SCRAPER_SCHEDULER ni nastavljen).")
        return None

    try:
        from apscheduler.schedulers.background import BackgroundScheduler
    except ImportError:
        logger.error("APScheduler ni nameščen. pip install APScheduler")
        return None

    _scrape_runner = scrape_runner_callback
    mode = os.environ.get("EVENT_SCRAPER_SCHEDULE_MODE", "daily").lower()
    days = int(os.environ.get("EVENT_SCRAPER_SCHEDULE_DAYS", "30"))
    run_at_start = os.environ.get("EVENT_SCRAPER_SCHEDULE_AT_START", "0").lower() in ("1", "true")

    _scheduler = BackgroundScheduler(daemon=True, timezone="Europe/Ljubljana")

    if mode == "daily":
        hour = int(os.environ.get("EVENT_SCRAPER_SCHEDULE_HOUR", "6"))
        minute = int(os.environ.get("EVENT_SCRAPER_SCHEDULE_MINUTE", "0"))
        _scheduler.add_job(
            _scheduled_run, "cron",
            hour=hour, minute=minute,
            kwargs={"days": days},
            id="daily_scrape",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=3600,  # do 1h zamude (npr. server bil dol)
        )
        logger.info(f"Scheduler VKLOPLJEN: dnevno ob {hour:02d}:{minute:02d} (Europe/Ljubljana), look-ahead {days} dni.")
    else:  # interval
        interval_min = int(os.environ.get("EVENT_SCRAPER_SCHEDULE_INTERVAL", "60"))
        _scheduler.add_job(
            _scheduled_run, "interval",
            minutes=interval_min,
            kwargs={"days": days},
            id="periodic_scrape",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        logger.info(f"Scheduler VKLOPLJEN: vsakih {interval_min} min, look-ahead {days} dni.")

    _scheduler.start()

    if run_at_start:
        threading.Timer(5.0, _scheduled_run, kwargs={"days": days}).start()

    return _scheduler


def _scheduled_run(days: int = 30):
    """Wrapper okoli _run_scrape_task da ne podvajamo če že teče."""
    try:
        if _scrape_runner is None:
            logger.warning("Scheduler je sprožen, a _scrape_runner ni registriran.")
            return
        logger.info(f"[SCHEDULER] Sprožam scheduled scrape (look-ahead {days} dni)...")
        _scrape_runner(days_ahead=days, media_id=None)
    except Exception as e:
        logger.exception(f"[SCHEDULER] Napaka: {e}")


def shutdown():
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
