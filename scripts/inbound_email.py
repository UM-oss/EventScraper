#!/usr/bin/env python3
"""
Email-to-Event sinhronizacija (samohostan, brez 3rd party).

Vsakih 15 min preko IMAP preveri inbox za nove maile, jih parsira
(Gemini AI), in ustvari Event zapise v bazi.

ENV:
  EVENT_SCRAPER_DATABASE_URL — PostgreSQL URL (Render)
  GEMINI_API_KEY             — za parsing nestrukturiranih mailov
  INBOUND_IMAP_HOST          — privzeto imap.gmail.com
  INBOUND_IMAP_PORT          — privzeto 993
  INBOUND_IMAP_USER          — npr. dogodki@gmail.com
  INBOUND_IMAP_PASSWORD      — Gmail App Password (NE navadno geslo!)
  INBOUND_IMAP_FOLDER        — privzeto INBOX
  INBOUND_DEFAULT_MEDIA      — comma-separated (npr. "mariborinfo,sobotainfo")
                               če pošiljatelj ne navede medija
  INBOUND_MAX_PER_RUN        — privzeto 20 (varovalka proti spam-u)
"""

import os
import sys
import re
import imaplib
import email
import json
import logging
import hashlib
from email.header import decode_header
from datetime import datetime, date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("inbound_email")

from database.models import get_db, Event, MediaOutlet, event_media, EventEdit
from scraper.dedup import compute_dedup_hash, check_dedup, DedupConfig
from scraper.categorizer import categorize_event


# ============================================================
# Email parsing helpers
# ============================================================

def _decode_header_safely(header_val):
    if not header_val:
        return ""
    try:
        decoded = decode_header(header_val)
        return "".join(
            (b.decode(charset or "utf-8", errors="replace") if isinstance(b, bytes) else b)
            for b, charset in decoded
        )
    except Exception:
        return str(header_val)


def _extract_text_body(msg):
    """Vrne plain-text body (preferiramo text/plain, fallback text/html → plain)."""
    text_parts = []
    html_parts = []
    for part in msg.walk():
        ct = part.get_content_type()
        cd = str(part.get("Content-Disposition", "")).lower()
        if "attachment" in cd:
            continue
        if ct == "text/plain":
            try:
                text_parts.append(part.get_payload(decode=True).decode(
                    part.get_content_charset() or "utf-8", errors="replace"))
            except Exception:
                pass
        elif ct == "text/html":
            try:
                html_parts.append(part.get_payload(decode=True).decode(
                    part.get_content_charset() or "utf-8", errors="replace"))
            except Exception:
                pass

    if text_parts:
        return "\n\n".join(text_parts).strip()
    if html_parts:
        # Basic HTML strip
        from bs4 import BeautifulSoup
        return BeautifulSoup("\n".join(html_parts), "html.parser").get_text(
            separator="\n", strip=True)
    return ""


def _extract_first_image_attachment(msg):
    """Vrne prvi image attachment kot (filename, data_url) ali None.
    Slika se pretvori v data: URL za shranjevanje v Event.image_url."""
    import base64
    for part in msg.walk():
        ct = part.get_content_type()
        if ct.startswith("image/"):
            try:
                data = part.get_payload(decode=True)
                if not data or len(data) > 5_000_000:  # max 5MB
                    continue
                filename = part.get_filename() or "image"
                b64 = base64.b64encode(data).decode("ascii")
                return filename, f"data:{ct};base64,{b64}"
            except Exception:
                continue
    return None


# ============================================================
# Gemini AI parsing
# ============================================================

def _ai_parse_event(subject: str, body: str) -> dict:
    """Z Gemini Flash izvleci strukturirane podatke iz email vsebine.

    Vrne dict z: title, date_start, time_start, location, organizer,
    description, event_type, suggested_media (seznam media_id-jev).
    Manjkajoča polja so None.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.warning("GEMINI_API_KEY ni nastavljen — uporabljam fallback parsing")
        return _heuristic_parse(subject, body)

    import requests

    prompt = f"""Iz emailskega sporočila izvleci podatke o dogodku in vrni SAMO valid JSON
v točno tej obliki (brez markdown, brez komentarjev):

{{
  "title": "naslov dogodka (povzemek če ni jasen)",
  "date_start": "YYYY-MM-DD ali null",
  "time_start": "HH:MM ali null",
  "location": "prizorišče (lokacija/dvorana) ali null",
  "organizer": "organizator ali null",
  "description": "kratek opis (2-3 stavki) ali null",
  "event_type": "ena od: glasba, kultura, literatura, predstava, sport, sejmi, za otroke, ostalo",
  "suggested_media": ["mariborinfo", "ptujinfo", "sobotainfo", "ljubljanainfo", "gorenjskainfo", "dolenjskainfo", "pomurec", "slovenija"]
}}

Pravila:
- Pusti polje na null če ni jasno iz vsebine.
- "suggested_media": izberi 1-3 medije glede na lokacijo/regijo dogodka.
  - Maribor → mariborinfo (možno tudi ptujinfo)
  - Ptuj/Ormož → ptujinfo
  - Murska Sobota/Lendava → sobotainfo, pomurec
  - Ljubljana → ljubljanainfo
  - Kranj/Bled/Bohinj → gorenjskainfo
  - Novo mesto/Krško/Sevnica → dolenjskainfo
  - Drugo/nacionalno → slovenija
- "event_type": uporabi natančno enega izmed naštetih nizov.

NASLOV: {subject}

VSEBINA:
{body[:3000]}
"""

    try:
        resp = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
            params={"key": api_key},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.2, "maxOutputTokens": 800,
                                      "responseMimeType": "application/json"},
            },
            timeout=20,
        )
        if resp.status_code != 200:
            logger.warning(f"Gemini error {resp.status_code}: {resp.text[:200]}")
            return _heuristic_parse(subject, body)
        data = resp.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        result = json.loads(text)
        logger.info(f"AI parsed: title='{result.get('title', '')[:40]}' date={result.get('date_start')}")
        return result
    except Exception as e:
        logger.warning(f"Gemini parsing failed: {e}; uporabljam heuristic")
        return _heuristic_parse(subject, body)


def _heuristic_parse(subject: str, body: str) -> dict:
    """Fallback brez AI: regex-based ekstrakcija."""
    text = f"{subject}\n{body}"

    # Datum: 22.4.2026 / 22. 4. 2026 / 22-04-2026
    date_match = re.search(r'(\d{1,2})\.\s*(\d{1,2})\.\s*(20\d{2})', text)
    if not date_match:
        date_match = re.search(r'(\d{1,2})-(\d{1,2})-(20\d{2})', text)
    iso_date = None
    if date_match:
        try:
            d = date(int(date_match.group(3)), int(date_match.group(2)), int(date_match.group(1)))
            iso_date = d.isoformat()
        except (ValueError, IndexError):
            pass

    # Ura: 19:00 / 19.00 / ob 19.00
    time_match = re.search(r'\b(\d{1,2})[:.](\d{2})\b', text)
    iso_time = None
    if time_match:
        h, m = int(time_match.group(1)), int(time_match.group(2))
        if 0 <= h <= 23 and 0 <= m <= 59:
            iso_time = f"{h:02d}:{m:02d}"

    return {
        "title": subject.strip()[:200] or "Dogodek iz emaila",
        "date_start": iso_date,
        "time_start": iso_time,
        "location": None,
        "organizer": None,
        "description": body[:500].strip() if body else None,
        "event_type": "ostalo",
        "suggested_media": ["slovenija"],
    }


# ============================================================
# Glavni proces
# ============================================================

def _create_event_from_email(parsed: dict, subject: str, sender: str,
                              image_data_url: str = None) -> tuple[bool, str]:
    """Ustvari Event v bazi iz parsanih podatkov.
    Vrne (created: bool, message: str)."""
    title = (parsed.get("title") or "").strip()[:500]
    date_start_str = parsed.get("date_start")
    if not title or not date_start_str:
        return False, "ni naslova ali datuma"

    try:
        date_start = date.fromisoformat(date_start_str)
    except ValueError:
        return False, f"neveljaven datum: {date_start_str}"

    if date_start < date.today():
        return False, "dogodek je v preteklosti"

    time_start = parsed.get("time_start") or None
    location = (parsed.get("location") or "").strip()[:500] or None
    organizer = (parsed.get("organizer") or "").strip()[:300] or None
    description = (parsed.get("description") or "").strip() or None
    event_type = parsed.get("event_type") or "ostalo"

    # Source ID: stabilen UUID iz email vsebine (za dedup re-deliveries)
    source_event_id = hashlib.sha256(
        f"{sender}|{subject}|{date_start_str}|{time_start or ''}".encode()
    ).hexdigest()[:32]

    with get_db() as db:
        # Dedup: če smo isti email že obdelali, vrni
        existing = db.query(Event).filter(
            Event.source_id == "email-inbound",
            Event.source_event_id == source_event_id,
        ).first()
        if existing:
            return False, f"že obdelan (event_id={existing.id})"

        # Fuzzy dedup proti vsem dogodkom
        dedup_result = check_dedup(db, title, date_start,
                                    time_start=time_start,
                                    location=location)
        if dedup_result.decision == "duplicate":
            return False, f"fuzzy duplicate of event_id={dedup_result.matched_event_id}"

        dedup_hash = compute_dedup_hash(title, date_start, location)
        event = Event(
            title=title,
            description=description,
            date_start=date_start,
            time_start=time_start,
            location=location,
            organizer=organizer,
            event_type=event_type,
            image_url=image_data_url,
            image_source="email" if image_data_url else None,
            description_source="manual" if description else None,
            source_id="email-inbound",
            source_event_id=source_event_id,
            region="email",
            dedup_hash=dedup_hash,
            is_active=True,
            first_seen_at=datetime.utcnow(),
            last_seen_at=datetime.utcnow(),
            last_scraped_at=datetime.utcnow(),
        )
        # NE re-categorize (uporabnikova preferenca: samo nove iz scrape-a)
        # Ampak email IS new — naj kategoriziramo samo če AI ni dal valid event_type
        if not event.event_type or event.event_type == "ostalo":
            categorize_event(event)
        event.completeness = event.calculate_completeness()
        db.add(event)
        db.flush()

        # Dodeli na predlagane medije
        suggested = parsed.get("suggested_media") or []
        if not suggested:
            default = (os.environ.get("INBOUND_DEFAULT_MEDIA", "slovenija")
                       .replace(" ", "").split(","))
            suggested = [m for m in default if m]

        valid_media = {m.id for m in db.query(MediaOutlet).all()}
        for mid in suggested:
            if mid not in valid_media:
                continue
            db.execute(event_media.insert().values(
                event_id=event.id, media_id=mid, status="new",
                assigned_at=datetime.utcnow(),
            ))

        # Audit
        db.add(EventEdit(
            event_id=event.id,
            field_name="created",
            old_value=None,
            new_value=f"email from {sender}",
            source="email-inbound",
            user_id=None,
        ))

        return True, f"event_id={event.id}, title='{title[:40]}', media={suggested}"


def main():
    host = os.environ.get("INBOUND_IMAP_HOST", "imap.gmail.com")
    port = int(os.environ.get("INBOUND_IMAP_PORT", "993"))
    user = os.environ.get("INBOUND_IMAP_USER")
    password = os.environ.get("INBOUND_IMAP_PASSWORD")
    folder = os.environ.get("INBOUND_IMAP_FOLDER", "INBOX")
    max_per_run = int(os.environ.get("INBOUND_MAX_PER_RUN", "20"))

    if not user or not password:
        logger.error("INBOUND_IMAP_USER / INBOUND_IMAP_PASSWORD nista nastavljena")
        return 1

    logger.info(f"Connecting to {host}:{port} as {user}, folder={folder}")
    M = imaplib.IMAP4_SSL(host, port)
    try:
        M.login(user, password)
        M.select(folder)

        # Poišči neprebrane maile
        status, msg_ids = M.search(None, "UNSEEN")
        if status != "OK":
            logger.error(f"IMAP search failed: {status}")
            return 1
        ids = msg_ids[0].split()
        logger.info(f"Found {len(ids)} unread messages")

        if not ids:
            return 0

        processed = 0
        created = 0
        skipped = 0

        for msg_id in ids[:max_per_run]:
            try:
                status, data = M.fetch(msg_id, "(RFC822)")
                if status != "OK":
                    continue

                msg = email.message_from_bytes(data[0][1])
                subject = _decode_header_safely(msg.get("Subject", ""))
                sender = _decode_header_safely(msg.get("From", ""))
                body = _extract_text_body(msg)

                logger.info(f"Processing: '{subject[:60]}' from {sender[:40]}")

                # Parse
                parsed = _ai_parse_event(subject, body)

                # Image attachment
                img = _extract_first_image_attachment(msg)
                img_url = img[1] if img else None

                # Create
                ok, message = _create_event_from_email(parsed, subject, sender, img_url)
                processed += 1
                if ok:
                    created += 1
                    logger.info(f"  ✓ {message}")
                    # Označi kot prebran
                    M.store(msg_id, "+FLAGS", "\\Seen")
                else:
                    skipped += 1
                    logger.info(f"  - skipped: {message}")
                    # Vseeno označi kot prebran (sicer bo prišel v naslednjih run-ih)
                    M.store(msg_id, "+FLAGS", "\\Seen")
            except Exception as e:
                logger.exception(f"Error processing message {msg_id}: {e}")

        logger.info(f"Done: {processed} processed, {created} created, {skipped} skipped")
        return 0
    finally:
        try:
            M.close()
            M.logout()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
