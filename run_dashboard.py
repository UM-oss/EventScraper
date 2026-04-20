#!/usr/bin/env python3
"""
Zagon Flask dashboarda.

Razvoj:
    python run_dashboard.py

Produkcija (gunicorn):
    gunicorn -w 2 -b 0.0.0.0:5000 web.app:app

Env spremenljivke:
    EVENT_SCRAPER_DATABASE_URL  (sqlite:///... ali postgresql://...)
    EVENT_SCRAPER_SCHEDULER     (1 za vključitev periodičnega scrape-a)
    EVENT_SCRAPER_VALIDATE      (1 za validacijo YAML-ov ob startupu)
    FLASK_DEBUG                 (1 za debug mode)
"""

import sys
import os
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Naloži .env če obstaja
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Strukturirano logiranje
from scraper.observability import setup_logging
setup_logging()

from database.models import init_db, database_info
from scraper.config_schema import assert_valid_or_die
from scraper.scheduler import init_scheduler
from scraper.bootstrap import bootstrap_media_outlets

# Validiraj YAML konfiguracije pred startupom (lahko se izklopi)
if os.environ.get("EVENT_SCRAPER_VALIDATE", "1").lower() in ("1", "true"):
    config_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")
    assert_valid_or_die(config_dir)

# Inicializiraj DB (samo če ne uporabljamo Alembic-a)
if os.environ.get("EVENT_SCRAPER_INIT_DB", "0").lower() in ("1", "true"):
    init_db()

# Bootstrap MediaOutlet zapisov iz media.yaml (idempotenten)
try:
    bootstrap_media_outlets()
except Exception as e:
    print(f"Bootstrap warning: {e}")

# Importiraj app šele po setup-u
from web.app import app, _run_scrape_task  # noqa: E402

# Scheduler (opcijski)
init_scheduler(_run_scrape_task)

if __name__ == "__main__":
    db_info = database_info()
    print(f"Database: {db_info['url']} ({db_info['dialect']})")
    debug_mode = os.environ.get("FLASK_DEBUG", "1").lower() in ("1", "true", "yes")
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port, debug=debug_mode, use_reloader=False)
