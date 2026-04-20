#!/usr/bin/env python3
"""
Zagonski skript za dnevni scraping.
Namenjen za poganjanje preko cron joba.

Uporaba:
    python run_scraper.py          # scraping vseh virov
    python run_scraper.py --test   # testni zagon (samo prvi vir)
"""

import sys
import os
import logging
from datetime import datetime

# Nastavi pot
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scraper.engine import ScraperEngine
from database.models import init_db


def setup_logging():
    """Nastavi logiranje v datoteko in konzolo"""
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
    os.makedirs(log_dir, exist_ok=True)

    log_file = os.path.join(log_dir, f"scrape_{datetime.now().strftime('%Y%m%d_%H%M')}.log")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ]
    )
    return logging.getLogger("scraper")


def main():
    logger = setup_logging()
    logger.info("=" * 50)
    logger.info("ZAČETEK SCRAPINGA")
    logger.info("=" * 50)

    # Inicializiraj bazo
    init_db()

    engine = ScraperEngine()

    if "--test" in sys.argv:
        # Testni način: samo prvi vir
        sources = engine.load_sources()
        if sources:
            logger.info(f"TESTNI NAČIN: samo vir '{sources[0].name}'")
            result = engine.scrape_source(sources[0])
            logger.info(f"Rezultat: {result}")
        else:
            logger.error("Ni najdenih virov!")
    else:
        # Polni zagon
        results = engine.run_all()
        logger.info("\n=== POVZETEK ===")
        total_new = 0
        for source_id, result in results.items():
            if "error" in result:
                logger.error(f"  {source_id}: NAPAKA - {result['error']}")
            else:
                logger.info(
                    f"  {source_id}: {result['new']} novih, "
                    f"{result['duplicates']} duplikatov"
                )
                total_new += result.get("new", 0)
        logger.info(f"\nSkupaj novih dogodkov: {total_new}")

    logger.info("=" * 50)
    logger.info("KONEC SCRAPINGA")
    logger.info("=" * 50)


if __name__ == "__main__":
    main()
