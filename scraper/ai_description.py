"""
AI generiranje promocijskih najav z Gemini Flash.
Vsaka uporaba je ROČNA (uporabniški klik), z varovalkami za brezplačni tier.

Brezplačni tier Gemini 2.5 Flash (April 2026):
- 10 zahtev/minuto
- 250 zahtev/dan
- 250.000 tokenov/minuto

Naša omejitev (z rezervo):
- 8 zahtev/minuto
- 200 zahtev/dan
"""

import os
import time
import json
import logging
import threading
from collections import deque
from datetime import datetime, date

import requests

logger = logging.getLogger(__name__)

GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_API_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent"
)

# Varovalke za brezplačni tier (z rezervo)
RATE_LIMIT_PER_MIN = 8
RATE_LIMIT_PER_DAY = 200

# Stanje (in-memory; ob restartu se resetira — varno za rate-limit)
_rate_lock = threading.Lock()
_request_timestamps = deque()  # zadnjih N timestamps
_daily_count = {"date": None, "count": 0}


def _get_api_key():
    """Pridobi API ključ iz okolice ali config/auth.yaml."""
    key = os.environ.get("GEMINI_API_KEY")
    if key:
        return key
    # Probaj iz auth.yaml
    try:
        import yaml
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "config", "auth.yaml"
        )
        if os.path.exists(path):
            with open(path, "r") as f:
                cfg = yaml.safe_load(f) or {}
            return cfg.get("gemini_api_key")
    except Exception:
        pass
    return None


def _check_rate_limit():
    """Preveri ali smo znotraj rate limit-a.
    Vrne (ok: bool, razlog: str)."""
    with _rate_lock:
        now = time.time()
        today = date.today().isoformat()

        # Resetiraj dnevni štetje če smo na novem dnevu
        if _daily_count["date"] != today:
            _daily_count["date"] = today
            _daily_count["count"] = 0

        # Dnevni limit
        if _daily_count["count"] >= RATE_LIMIT_PER_DAY:
            return False, f"Dnevna meja {RATE_LIMIT_PER_DAY} zahtev je dosežena. Poskusite jutri."

        # Pobriši stare timestamp-e (starejše od 60s)
        cutoff = now - 60
        while _request_timestamps and _request_timestamps[0] < cutoff:
            _request_timestamps.popleft()

        # Minutni limit
        if len(_request_timestamps) >= RATE_LIMIT_PER_MIN:
            wait = int(_request_timestamps[0] + 60 - now) + 1
            return False, f"Preveč zahtev v zadnji minuti. Počakajte ~{wait}s."

        return True, ""


def _record_request():
    """Beleži uspešno zahtevo za rate-limiting."""
    with _rate_lock:
        _request_timestamps.append(time.time())
        today = date.today().isoformat()
        if _daily_count["date"] != today:
            _daily_count["date"] = today
            _daily_count["count"] = 0
        _daily_count["count"] += 1


def get_usage_stats():
    """Vrne trenutno porabo za prikaz v UI."""
    with _rate_lock:
        now = time.time()
        cutoff = now - 60
        recent = sum(1 for t in _request_timestamps if t > cutoff)
        today = date.today().isoformat()
        if _daily_count["date"] != today:
            return {"per_min": 0, "per_min_max": RATE_LIMIT_PER_MIN,
                    "per_day": 0, "per_day_max": RATE_LIMIT_PER_DAY}
        return {
            "per_min": recent,
            "per_min_max": RATE_LIMIT_PER_MIN,
            "per_day": _daily_count["count"],
            "per_day_max": RATE_LIMIT_PER_DAY,
        }


def generate_event_description(event):
    """Generiraj promocijsko najavo za dogodek z Gemini Flash.

    Vrne dict: {ok: bool, description?: str, error?: str}
    """
    api_key = _get_api_key()
    if not api_key:
        return {"ok": False, "error": "GEMINI_API_KEY ni nastavljen. Dodaj v config/auth.yaml ali okolico."}

    ok, reason = _check_rate_limit()
    if not ok:
        return {"ok": False, "error": reason}

    # Pripravi kontekst
    parts = [f"Naslov: {event.title}"]
    if event.event_type:
        parts.append(f"Tip dogodka: {event.event_type}")
    if event.date_start:
        d = event.date_start.strftime("%d. %m. %Y")
        if event.time_start:
            d += f" ob {event.time_start}"
        parts.append(f"Datum: {d}")
    if event.location:
        parts.append(f"Prizorišče: {event.location}")
    if event.organizer:
        parts.append(f"Organizator: {event.organizer}")
    if event.price:
        parts.append(f"Vstopnina: {event.price}")
    context = "\n".join(parts)

    prompt = (
        "Napiši kratko, 2-3 stavčno promocijsko najavo dogodka v slovenščini. "
        "Uporabi SAMO podatke ki so spodaj — NE izmišljaj programa, gostov, podrobnosti, "
        "umetnikov ali zgodovine, ki jih ni v podatkih. "
        "Ton naj bo vabljiv, a stvaren. Ne uporabljaj klišejev. "
        "Ne začni s 'Pridružite se', 'Vabljeni' ali podobnimi frazami. "
        "Vrni samo besedilo opisa, brez dodatnih navedb.\n\n"
        f"PODATKI:\n{context}"
    )

    try:
        resp = requests.post(
            GEMINI_API_URL,
            params={"key": api_key},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.4,
                    "maxOutputTokens": 250,
                },
            },
            timeout=15,
        )
        if resp.status_code != 200:
            err = resp.text[:200]
            logger.warning(f"Gemini API napaka {resp.status_code}: {err}")
            return {"ok": False, "error": f"API napaka {resp.status_code}: {err}"}

        data = resp.json()
        candidates = data.get("candidates") or []
        if not candidates:
            return {"ok": False, "error": "Gemini ni vrnil rezultata."}
        text_parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in text_parts).strip()

        if not text:
            return {"ok": False, "error": "Prazen odgovor."}

        # Beleži šele ob USPEHU
        _record_request()
        return {"ok": True, "description": text}

    except requests.Timeout:
        return {"ok": False, "error": "Časovna omejitev (15s)."}
    except Exception as e:
        logger.exception("Napaka pri klicu Gemini")
        return {"ok": False, "error": str(e)}
