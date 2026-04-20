"""
Webhook notifikacije po koncu scrape-a.

Konfiguracija prek env spremenljivk:
  EVENT_SCRAPER_WEBHOOK_URL    — POST URL (Slack, Discord, Teams, custom)
  EVENT_SCRAPER_WEBHOOK_TYPE   — slack | discord | generic (default: generic)
  EVENT_SCRAPER_WEBHOOK_MIN_NEW — minimalno število novih dogodkov za sprožitev
                                   (default: 1)
"""

import os
import logging
from typing import Optional

import requests

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 5


def _get_config():
    return {
        "url": os.environ.get("EVENT_SCRAPER_WEBHOOK_URL"),
        "type": os.environ.get("EVENT_SCRAPER_WEBHOOK_TYPE", "generic").lower(),
        "min_new": int(os.environ.get("EVENT_SCRAPER_WEBHOOK_MIN_NEW", "1")),
    }


def notify_scrape_complete(result: dict):
    """Pošlji webhook po koncu scrape-a.

    `result` = {total_new, total_updated, total_stale, sources_ok,
                sources_err, duration_s, errors}
    """
    cfg = _get_config()
    if not cfg["url"]:
        return False

    new_count = result.get("total_new", 0)
    if new_count < cfg["min_new"]:
        logger.debug(f"Webhook skipped (new={new_count} < min_new={cfg['min_new']})")
        return False

    msg_text = (
        f"Event scrape končan: "
        f"*{new_count}* novih, "
        f"*{result.get('total_updated', 0)}* posodobljenih, "
        f"*{result.get('total_stale', 0)}* označenih kot neaktivni "
        f"iz {result.get('sources_ok', 0)} virov "
        f"({result.get('sources_err', 0)} napak) "
        f"v {result.get('duration_s', 0)}s."
    )

    payload = _build_payload(cfg["type"], msg_text, result)
    try:
        resp = requests.post(cfg["url"], json=payload, timeout=DEFAULT_TIMEOUT)
        if resp.status_code >= 400:
            logger.warning(f"Webhook neuspešen: HTTP {resp.status_code}")
            return False
        logger.info("Webhook poslan.")
        return True
    except Exception as e:
        logger.warning(f"Webhook napaka: {e}")
        return False


def _build_payload(webhook_type: str, text: str, result: dict) -> dict:
    if webhook_type == "slack":
        return {"text": text, "mrkdwn": True}
    if webhook_type == "discord":
        return {"content": text}
    # generic / custom
    return {
        "text": text.replace("*", ""),
        "result": result,
    }
