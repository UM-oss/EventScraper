"""
Flask dashboard in Drupal API za pregled, urejanje in objavo dogodkov.
Avtentikacija z email/geslo (uporabniki definirani v config/auth.yaml).

Dodajanje uporabnika:
  1. Generiraj hash: python3 -c "import bcrypt; print(bcrypt.hashpw(b'GESLO', bcrypt.gensalt()).decode())"
  2. Dodaj v config/auth.yaml pod users:
"""

import os
import sys
import io
import re
import json
import time
import zipfile
import secrets
import functools
from datetime import datetime, date, timedelta

import yaml
import bcrypt
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, abort, send_file

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.models import (
    Session as DBSession, Event, MediaOutlet, ScrapeLog, DrupalPushLog,
    SourceHealth, UnprocessedUrl, event_media, init_db, get_db,
    User, EventEdit, database_info,
)
from sqlalchemy import and_, func, or_ as sa_or

# ============================================================
# APP SETUP
# ============================================================

app = Flask(__name__)

# Naloži auth config
CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")
auth_config_path = os.path.join(CONFIG_DIR, "auth.yaml")

if os.path.exists(auth_config_path):
    with open(auth_config_path, "r") as f:
        auth_config = yaml.safe_load(f) or {}
else:
    auth_config = {"users": []}

# Secret key — vrstni red: ENV var → auth.yaml → auto-generate
_secret = os.environ.get("EVENT_SCRAPER_SECRET_KEY") or auth_config.get("secret_key")
if not _secret or _secret == "null" or "ZAMENJAJ" in str(_secret):
    _secret = secrets.token_hex(32)
    auth_config["secret_key"] = _secret
    try:
        os.makedirs(os.path.dirname(auth_config_path), exist_ok=True)
        with open(auth_config_path, "w") as f:
            yaml.dump(auth_config, f, default_flow_style=False, allow_unicode=True)
    except (OSError, PermissionError):
        # Read-only filesystem (npr. Vercel) — secret živi samo v RAM-u, dokler proces teče
        pass

app.secret_key = _secret
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("SESSION_SECURE", "0").lower() in ("1", "true")
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=7)


# CSRF zaščita za POST/PUT/DELETE
def _get_or_set_csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


@app.before_request
def _check_csrf():
    """Zahteva X-CSRF-Token header za state-changing zahteve.

    Login je izvzet (ima svoj rate-limit). API zahteve od JS klienta morajo
    pošiljati header (frontend ga prebere iz <meta name='csrf-token'> ali
    iz /auth/status odgovora).
    """
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return None
    if request.endpoint in ("login", "static"):
        return None
    if not session.get("user_email"):
        return None  # auth_required bo to obravnavalo
    expected = session.get("csrf_token")
    sent = request.headers.get("X-CSRF-Token") or (
        request.get_json(silent=True) or {}
    ).get("_csrf")
    if not expected or not sent or sent != expected:
        return jsonify({"error": "csrf_token_missing_or_invalid"}), 403


@app.context_processor
def _inject_csrf():
    return {
        "csrf_token": _get_or_set_csrf_token(),
        "is_admin_user": is_admin() if session.get("user_email") else False,
    }

# Naloži uporabnike iz YAML-a
AUTH_USERS = {}
for u in auth_config.get("users", []):
    email = u.get("email", "").lower()
    if email:
        AUTH_USERS[email] = {
            "name": u.get("name", email),
            "password_hash": u.get("password_hash", ""),
        }


# ============================================================
# KONSTANTE IN VALIDACIJA
# ============================================================

VALID_STATUSES = {"new", "approved", "queued", "pushed", "published", "skipped", "archived"}
VALID_TRANSITIONS = {
    "new": {"approved", "skipped"},
    "approved": {"queued", "skipped"},
    "queued": {"pushed", "approved"},
    "pushed": {"published", "queued"},
    "published": {"archived"},
    "skipped": {"new"},
    "archived": set(),
}


def get_json_or_400():
    """Varno preberi JSON iz requesta, vrni 400 če ni veljavno."""
    data = request.get_json(silent=True)
    if data is None:
        abort(400, description="Neveljaven JSON v telesu zahteve")
    return data


def validate_status(status):
    """Preveri ali je status veljaven."""
    if status not in VALID_STATUSES:
        abort(400, description=f"Neveljaven status: {status}. Dovoljeni: {', '.join(sorted(VALID_STATUSES))}")
    return status


def get_or_create_user(db, email: str, name: str = None):
    """Vrne User zapis za trenutnega prijavljenega uporabnika.
    Ustvari ga, če še ne obstaja (sinhronizacija iz auth.yaml v DB)."""
    if not email:
        return None
    user = db.query(User).filter(User.email == email.lower()).first()
    if user is None:
        user = User(email=email.lower(), name=name or email)
        db.add(user)
        db.flush()
    return user


def current_user_id(db):
    """ID trenutno prijavljenega uporabnika v DB. Sproži create če manjka."""
    email = session.get("user_email")
    if not email:
        return None
    name = session.get("user_name")
    user = get_or_create_user(db, email, name)
    return user.id if user else None


def is_admin():
    """Trenutno prijavljen uporabnik ima role='admin'."""
    email = session.get("user_email")
    if not email:
        return False
    with get_db() as db:
        u = db.query(User).filter(User.email == email.lower()).first()
        return bool(u and u.role == "admin")


def admin_required(f):
    """Dekorator: samo admin-i."""
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user_email"):
            if request.path.startswith("/api/"):
                return jsonify({"error": "Unauthorized"}), 401
            return redirect(url_for("login"))
        if not is_admin():
            if request.path.startswith("/api/"):
                return jsonify({"error": "Admin access required"}), 403
            return "Samo admin lahko dostopa do te strani.", 403
        return f(*args, **kwargs)
    return decorated


def current_user_allowed_media(db):
    """Vrne seznam dovoljenih media ID-jev za trenutnega uporabnika.
    None = admin (vsi); seznam = omejen urednik."""
    import json as _json
    email = session.get("user_email")
    if not email:
        return []
    user = db.query(User).filter(User.email == email.lower()).first()
    if user is None or user.role == "admin":
        return None  # vsi
    if user.allowed_media:
        try:
            return _json.loads(user.allowed_media)
        except Exception:
            return []
    return []


def log_event_edit(db, event, field_name, old_value, new_value, source="manual"):
    """Zabeleži spremembo polja v event_edits."""
    db.add(EventEdit(
        event_id=event.id,
        field_name=field_name,
        old_value=str(old_value) if old_value is not None else None,
        new_value=str(new_value) if new_value is not None else None,
        source=source,
        user_id=current_user_id(db),
    ))


# ============================================================
# AUTH
# ============================================================

def auth_required(f):
    """Dekorator ki zahteva prijavo. Brez uporabnikov vrne napako."""
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not AUTH_USERS:
            # Ni definiranih uporabnikov — zakleni dostop
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"error": "Ni definiranih uporabnikov. Dodaj z: python3 manage_users.py add"}), 503
            return "Ni definiranih uporabnikov. Dodaj z: python3 manage_users.py add", 503
        if not session.get("user_email"):
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"error": "Unauthorized"}), 401
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


@app.route("/login", methods=["GET", "POST"])
def login():
    if not AUTH_USERS:
        return "Ni definiranih uporabnikov. Dodaj z: python3 manage_users.py add", 503

    if session.get("user_email"):
        return redirect(url_for("index"))

    error = None
    if request.method == "POST":
        client_ip = request.remote_addr or "unknown"

        # Rate limiting
        if _check_rate_limit(client_ip):
            error = "Preveč neuspešnih poskusov. Počakaj 5 minut."
            return render_template("login.html", error=error)

        email = request.form.get("email", "").lower().strip()
        password = request.form.get("password", "")

        # 1. Poskusi DB User.password_hash (primary, persistira na Render)
        password_hash = None
        user_name = email
        try:
            with get_db() as db:
                db_user = db.query(User).filter(User.email == email).first()
                if db_user and db_user.is_active and db_user.password_hash:
                    password_hash = db_user.password_hash
                    user_name = db_user.name or email
        except Exception:
            pass

        # 2. Fallback na auth.yaml (legacy / bootstrap admin)
        if not password_hash:
            user_yaml = AUTH_USERS.get(email)
            if user_yaml and user_yaml.get("password_hash"):
                password_hash = user_yaml["password_hash"]
                user_name = user_yaml.get("name", email)

        if password_hash and bcrypt.checkpw(password.encode(), password_hash.encode()):
            session["user_email"] = email
            session["user_name"] = user_name
            session.permanent = True
            _login_attempts.pop(client_ip, None)
            try:
                with get_db() as db:
                    u = get_or_create_user(db, email, user_name)
                    u.last_login_at = datetime.utcnow()
                    # Migriraj password_hash iz yaml v DB če manjka
                    if not u.password_hash:
                        u.password_hash = password_hash
            except Exception:
                pass
            return redirect(url_for("index"))

        _record_attempt(client_ip)
        error = "Napačen email ali geslo"

    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/auth/status")
def auth_status():
    if not AUTH_USERS:
        return jsonify({"authenticated": True, "mode": "development"})

    if session.get("user_email"):
        return jsonify({
            "authenticated": True,
            "email": session["user_email"],
            "name": session.get("user_name", ""),
            "csrf_token": _get_or_set_csrf_token(),
        })

    return jsonify({"authenticated": False}), 401


# ============================================================
# RATE LIMITING (preprost in-memory)
# ============================================================

_login_attempts = {}  # {ip: [(timestamp, ...]}

def _check_rate_limit(ip, max_attempts=5, window=300):
    """Preprost rate limiter za login. Vrne True če preseženo."""
    now = time.time()
    attempts = _login_attempts.get(ip, [])
    attempts = [t for t in attempts if now - t < window]
    _login_attempts[ip] = attempts
    if len(attempts) >= max_attempts:
        return True
    return False

def _record_attempt(ip):
    _login_attempts.setdefault(ip, []).append(time.time())


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(400)
def bad_request(e):
    if request.is_json or request.path.startswith("/api/"):
        return jsonify({"error": str(e.description)}), 400
    return str(e.description), 400

@app.errorhandler(404)
def not_found(e):
    if request.is_json or request.path.startswith("/api/"):
        return jsonify({"error": "Ni najdeno"}), 404
    return "Stran ni najdena", 404

@app.errorhandler(500)
def server_error(e):
    if request.is_json or request.path.startswith("/api/"):
        return jsonify({"error": "Notranja napaka strežnika"}), 500
    return "Notranja napaka strežnika", 500


# ============================================================
# DASHBOARD
# ============================================================

@app.route("/")
@auth_required
def index():
    """Glavna stran — seznam novih dogodkov"""
    with get_db() as db:
        # Filtri — privzeto vedno DANES + 30 dni
        today = date.today()
        media_id = request.args.get("media", "")
        date_from_raw = request.args.get("from")
        date_to_raw = request.args.get("to")

        # Če uporabnik ni izrecno podal "from" ali je iz preteklosti → DANES
        try:
            if not date_from_raw or date.fromisoformat(date_from_raw) < today:
                date_from = today.isoformat()
            else:
                date_from = date_from_raw
        except ValueError:
            date_from = today.isoformat()

        # Če "to" ni podan ali je pred "from" → from + 30 dni
        try:
            df = date.fromisoformat(date_from)
            if not date_to_raw or date.fromisoformat(date_to_raw) < df:
                date_to = (df + timedelta(days=30)).isoformat()
            else:
                date_to = date_to_raw
        except ValueError:
            date_to = (today + timedelta(days=30)).isoformat()
        status = request.args.get("status", "new")
        search = request.args.get("q", "")
        event_type = request.args.get("type", "")
        region = request.args.get("region", "")

        media_outlets = db.query(MediaOutlet).all()

        # Privzeto le aktivni dogodki; show_inactive=1 jih vključi
        show_inactive = request.args.get("show_inactive") in ("1", "true")
        query = db.query(Event).filter(
            Event.date_start >= date.fromisoformat(date_from),
            Event.date_start <= date.fromisoformat(date_to),
        )
        if not show_inactive:
            query = query.filter(Event.is_active == True)  # noqa: E712

        if media_id:
            query = query.join(event_media, event_media.c.event_id == Event.id).filter(
                event_media.c.media_id == media_id
            )
            if status and status != "all":
                query = query.filter(event_media.c.status == status)
        elif status and status != "all":
            # Brez izbranega medija: filtriraj po statusu v kateremkoli mediju
            from sqlalchemy import exists
            status_subq = exists().where(
                and_(
                    event_media.c.event_id == Event.id,
                    event_media.c.status == status
                )
            )
            query = query.filter(status_subq)

        if event_type:
            query = query.filter(Event.event_type == event_type)

        if region:
            query = query.filter(Event.region == region)

        if search:
            query = query.filter(
                Event.title.ilike(f"%{search}%") |
                Event.description.ilike(f"%{search}%") |
                Event.location.ilike(f"%{search}%") |
                Event.organizer.ilike(f"%{search}%")
            )

        page_num = int(request.args.get("p", 1))
        per_page = 30
        total_events = query.count()
        events = query.order_by(Event.date_start.asc()).offset(
            (page_num - 1) * per_page
        ).limit(per_page).all()
        total_pages = (total_events + per_page - 1) // per_page

        total_new = db.query(Event).filter(
            Event.date_start >= date.today(),
            Event.is_active == True,  # noqa: E712
        ).count()

        last_scrape = db.query(ScrapeLog).filter(
            ScrapeLog.finished_at != None
        ).order_by(
            ScrapeLog.finished_at.desc()
        ).first()

        # Pretvori UTC → lokalni čas (Europe/Ljubljana = CET/CEST)
        last_scrape_local = None
        if last_scrape and last_scrape.finished_at:
            try:
                from zoneinfo import ZoneInfo
                last_scrape_local = last_scrape.finished_at.replace(
                    tzinfo=ZoneInfo("UTC")
                ).astimezone(ZoneInfo("Europe/Ljubljana"))
            except Exception:
                # Fallback: enostavna +2h korekcija (CEST)
                last_scrape_local = last_scrape.finished_at + timedelta(hours=2)

        # Trajanje zadnje scrape "session" — sosednje skupine logov brez več kot 5 min razmika.
        # Tako ne vključimo prejšnjih ločenih runov v isti uri.
        last_scrape_duration = None
        if last_scrape and last_scrape.finished_at:
            recent = db.query(ScrapeLog).filter(
                ScrapeLog.started_at >= last_scrape.finished_at - timedelta(hours=2),
                ScrapeLog.started_at <= last_scrape.finished_at,
            ).order_by(ScrapeLog.started_at.desc()).all()
            session_start = last_scrape.started_at
            prev_started = last_scrape.started_at
            for log in recent[1:]:  # od najnovejšega naprej (preskoči zadnjega)
                if not log.started_at:
                    continue
                gap = (prev_started - log.started_at).total_seconds()
                if gap > 300:  # > 5 min razmika → drug session
                    break
                session_start = log.started_at
                prev_started = log.started_at
            last_scrape_duration = int((last_scrape.finished_at - session_start).total_seconds())

        regions = [r[0] for r in db.query(Event.region).distinct().all() if r[0]]
        event_types = [t[0] for t in db.query(Event.event_type).distinct().all() if t[0]]

        # Uporabniški podatki za template
        user_info = {}
        if session.get("user_email"):
            user_info = {
                "name": session.get("user_name", ""),
                "email": session.get("user_email", ""),
            }

        return render_template(
            "index.html",
            events=events,
            media_outlets=media_outlets,
            current_media=media_id,
            current_status=status,
            current_search=search,
            current_type=event_type,
            current_region=region,
            date_from=date_from,
            date_to=date_to,
            total_new=total_new,
            last_scrape=last_scrape,
            last_scrape_local=last_scrape_local,
            last_scrape_duration=last_scrape_duration,
            today=date.today().isoformat(),
            page_num=page_num,
            total_pages=total_pages,
            total_events=total_events,
            regions=regions,
            event_types=event_types,
            user=user_info,
        )


# ============================================================
# UREDNIŠKI API — status, odobritev, urejanje
# ============================================================

@app.route("/api/event/<int:event_id>/status", methods=["POST"])
@auth_required
def update_event_status(event_id):
    with get_db() as db:
        data = get_json_or_400()
        new_status = validate_status(data.get("status", "approved"))
        media_id = data.get("media_id", "")
        user_id = current_user_id(db)

        where_clause = event_media.c.event_id == event_id
        if media_id:
            where_clause = and_(where_clause, event_media.c.media_id == media_id)

        values = {"status": new_status, "processed_at": datetime.utcnow()}
        if new_status == "approved":
            values["approved_at"] = datetime.utcnow()
            values["approved_by_user_id"] = user_id
        elif new_status == "skipped":
            values["skipped_by_user_id"] = user_id

        db.execute(event_media.update().where(where_clause).values(**values))

        # Beleži v event_edits
        event = db.query(Event).get(event_id)
        if event:
            db.add(EventEdit(
                event_id=event.id,
                field_name=f"em_status{':' + media_id if media_id else ''}",
                old_value=None, new_value=new_status,
                source="manual", user_id=user_id,
            ))
        return jsonify({"ok": True, "status": new_status})


@app.route("/api/image-proxy")
@auth_required
def image_proxy():
    """Proxy za slike z domen ki blokirajo hotlinking (FB, ...).
    FB lookaside lahko vrne JS redirect HTML — sledimo do prave slike."""
    import re as _re
    import requests as _requests
    from flask import Response

    url = request.args.get("url", "")
    if not url or not url.startswith("http"):
        abort(400)

    # Za FB lookaside crawler: nujno facebookexternalhit user agent (drugače HTML redirect)
    is_fb_lookaside = "lookaside.fbsbx.com" in url or "fbcdn.net" in url
    if is_fb_lookaside:
        headers = {
            "User-Agent": "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)",
            "Accept": "*/*",
        }
    else:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            "Referer": "https://www.facebook.com/",
            "Accept-Language": "en-US,en;q=0.9,sl;q=0.8",
        }

    try:
        # Do 3 koraki - sledi JS redirect-om
        for _ in range(3):
            resp = _requests.get(url, headers=headers, timeout=10, allow_redirects=True)
            content_type = resp.headers.get("content-type", "")

            # Slika - vrni jo
            if content_type.startswith("image/"):
                return Response(
                    resp.content,
                    content_type=content_type,
                    headers={"Cache-Control": "public, max-age=3600"},
                )

            # HTML z JS location.href redirect - extract pravi URL
            if "html" in content_type:
                m = _re.search(r'location\.href\s*=\s*"([^"]+)"', resp.text)
                if m:
                    next_url = m.group(1).encode().decode("unicode_escape")
                    url = next_url
                    continue

                # Poskusi og:image
                m = _re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', resp.text)
                if m:
                    url = m.group(1)
                    continue

            break

        # Ne uspeh - 404
        abort(404, description="Slike ni mogoče pridobiti")
    except Exception as e:
        abort(500, description=str(e))


@app.route("/api/event/<int:event_id>/update-field", methods=["POST"])
@auth_required
def update_event_field(event_id):
    """Ročno posodobi posamezno polje dogodka.
    Podpira optimistic locking preko `expected_version` (opcijsko).
    """
    ALLOWED = {"location", "organizer", "event_type", "address",
               "price", "title", "description"}
    data = get_json_or_400()
    field = data.get("field")
    value = (data.get("value") or "").strip()
    expected_version = data.get("expected_version")

    if field not in ALLOWED:
        abort(400, description=f"Polje '{field}' ni dovoljeno za urejanje.")

    # Validacija event_type — samo 8 dovoljenih kategorij
    if field == "event_type" and value:
        from scraper.categorizer import ALLOWED_TYPES, normalize_event_type
        if value not in ALLOWED_TYPES:
            value = normalize_event_type(value)

    with get_db() as db:
        event = db.query(Event).get(event_id)
        if not event:
            abort(404)

        # Optimistic locking
        if expected_version is not None and event.version != expected_version:
            return jsonify({
                "ok": False,
                "error": "version_conflict",
                "message": "Dogodek je medtem urejal drug uporabnik. Osveži in poskusi znova.",
                "current_version": event.version,
            }), 409

        old_value = getattr(event, field, None)
        if str(old_value or "") == value:
            return jsonify({"ok": True, "field": field, "value": value, "no_change": True})

        setattr(event, field, value or None)
        # Označi vir spremembe
        if field == "description":
            event.description_source = "manual"
        event.version = (event.version or 1) + 1
        event.last_edited_by_user_id = current_user_id(db)
        event.last_edited_at = datetime.utcnow()

        log_event_edit(db, event, field, old_value, value, source="manual")
        return jsonify({
            "ok": True,
            "field": field,
            "value": value,
            "version": event.version,
        })


@app.route("/api/event/<int:event_id>/ai-description", methods=["POST"])
@auth_required
def ai_generate_description(event_id):
    """Generiraj opis dogodka z Gemini Flash AI (ROČNO, po kliku uporabnika)."""
    from scraper.ai_description import generate_event_description, get_usage_stats

    with get_db() as db:
        event = db.query(Event).get(event_id)
        if not event:
            abort(404)

        result = generate_event_description(event)
        if result.get("ok"):
            old_desc = event.description
            event.description = result["description"]
            event.description_source = "ai-generated"
            event.version = (event.version or 1) + 1
            event.last_edited_by_user_id = current_user_id(db)
            event.last_edited_at = datetime.utcnow()
            log_event_edit(db, event, "description", old_desc, result["description"],
                           source="ai-generated")
            return jsonify({
                "ok": True,
                "description": result["description"],
                "usage": get_usage_stats(),
            })
        return jsonify({
            "ok": False,
            "error": result.get("error", "Napaka"),
            "usage": get_usage_stats(),
        }), 429 if "meja" in (result.get("error") or "").lower() else 400


@app.route("/api/ai/usage")
@auth_required
def ai_usage():
    """Trenutna poraba AI free-tier quote."""
    from scraper.ai_description import get_usage_stats
    return jsonify(get_usage_stats())


@app.route("/api/event/<int:event_id>/fetch-description", methods=["POST"])
@auth_required
def fetch_event_description(event_id):
    """Poskusi pridobiti opis dogodka iz source_url."""
    from scraper.image_fallback import find_fallback_description
    with get_db() as db:
        event = db.query(Event).get(event_id)
        if not event:
            abort(404)
        force = request.args.get("force") in ("1", "true")
        desc = find_fallback_description(event)
        if desc:
            old = event.description
            # Ne prepiši krajšega obstoječega z še krajšim, razen če force
            if not force and old and len(old) >= len(desc) * 0.9:
                return jsonify({
                    "ok": False,
                    "error": "Najden opis ni daljši od obstoječega.",
                })
            event.description = desc
            event.description_source = "scraped"
            log_event_edit(db, event, "description", old, desc, source="auto-enrichment")
            return jsonify({"ok": True, "description": desc, "length": len(desc)})
        return jsonify({"ok": False, "error": "Opisa ni mogoče najti"})


@app.route("/api/event/<int:event_id>/set-image", methods=["POST"])
@auth_required
def set_event_image(event_id):
    """Ročno nastavi URL slike za dogodek (npr. uporabnik prilepi svojo)."""
    data = get_json_or_400()
    new_url = (data.get("image_url") or "").strip()
    if not new_url or not new_url.startswith("http"):
        abort(400, description="Veljavni URL slike je obvezen")

    with get_db() as db:
        event = db.query(Event).get(event_id)
        if not event:
            abort(404)
        old = event.image_url
        event.image_url = new_url
        event.image_source = "manual"
        # Pridobi dimenzije
        try:
            from scraper.image_fallback import _get_image_dimensions
            dims = _get_image_dimensions(new_url)
            if dims:
                event.image_width, event.image_height = dims
            else:
                event.image_width = event.image_height = None
        except Exception:
            event.image_width = event.image_height = None
        log_event_edit(db, event, "image_url", old, new_url, source="manual")
        return jsonify({
            "ok": True,
            "image_url": new_url,
            "width": event.image_width,
            "height": event.image_height,
        })


@app.route("/api/event/<int:event_id>/fetch-image", methods=["POST"])
@auth_required
def fetch_event_image(event_id):
    """Poskusi najti sliko za dogodek (og:image iz source_url, FB, venue, kategorija)."""
    from scraper.image_fallback import find_fallback_image

    with get_db() as db:
        event = db.query(Event).get(event_id)
        if not event:
            abort(404)

        image_url = find_fallback_image(event, force_fetch=True)
        if image_url:
            old = event.image_url
            event.image_url = image_url
            event.image_source = "fallback"
            log_event_edit(db, event, "image_url", old, image_url, source="auto-enrichment")
            return jsonify({"ok": True, "image_url": image_url})
        return jsonify({"ok": False, "error": "Slike ni mogoče najti"})


@app.route("/api/event/<int:event_id>/approve", methods=["POST"])
@auth_required
def approve_event(event_id):
    with get_db() as db:
        data = get_json_or_400()
        media_ids = data.get("media_ids", [])
        featured = data.get("featured", False)
        priority = data.get("priority", 0)
        editor_notes = data.get("editor_notes", "")

        if not media_ids:
            db.execute(
                event_media.update()
                .where(and_(
                    event_media.c.event_id == event_id,
                    event_media.c.status == "new"
                ))
                .values(
                    status="approved",
                    featured=featured,
                    priority=priority,
                    editor_notes=editor_notes,
                    approved_at=datetime.utcnow()
                )
            )
        else:
            for mid in media_ids:
                db.execute(
                    event_media.update()
                    .where(and_(
                        event_media.c.event_id == event_id,
                        event_media.c.media_id == mid
                    ))
                    .values(
                        status="approved",
                        featured=featured,
                        priority=priority,
                        editor_notes=editor_notes,
                        approved_at=datetime.utcnow()
                    )
                )

        return jsonify({"ok": True, "event_id": event_id, "status": "approved"})


@app.route("/api/event/<int:event_id>/featured", methods=["POST"])
@auth_required
def toggle_featured(event_id):
    """Toggle featured flag za en dogodek (na izbranem mediju ali vseh).

    Body: {"media_id": "mariborinfo", "featured": true|false}
    """
    data = get_json_or_400()
    media_id = data.get("media_id")
    featured = bool(data.get("featured", True))

    with get_db() as db:
        user_id = current_user_id(db)
        where = [event_media.c.event_id == event_id]
        if media_id:
            where.append(event_media.c.media_id == media_id)
        result = db.execute(
            event_media.update().where(and_(*where)).values(featured=featured)
        )
        db.add(EventEdit(
            event_id=event_id,
            field_name=f"featured{':' + media_id if media_id else ''}",
            old_value=str(not featured), new_value=str(featured),
            source="manual", user_id=user_id,
        ))
        return jsonify({
            "ok": True, "featured": featured,
            "rows_affected": result.rowcount,
        })


@app.route("/api/events/bulk-action", methods=["POST"])
@auth_required
def bulk_event_action():
    """Bulk operacija na več dogodkov hkrati.

    Body: {
      "event_ids": [1, 2, 3],
      "action": "approved" | "skipped" | "featured" | "unfeatured",
      "media_id": "mariborinfo"  (opcijsko: če manjka, deluje na vseh medijih)
    }
    """
    data = get_json_or_400()
    event_ids = data.get("event_ids") or []
    action = data.get("action")
    media_id = data.get("media_id") or None

    if not event_ids or not isinstance(event_ids, list):
        abort(400, description="event_ids mora biti neprazen seznam")
    if action not in ("approved", "skipped", "published", "featured", "unfeatured"):
        abort(400, description=f"Neveljavna action: {action}")

    with get_db() as db:
        user_id = current_user_id(db)
        # Sestavi where clause
        where_clauses = [event_media.c.event_id.in_(event_ids)]
        if media_id:
            where_clauses.append(event_media.c.media_id == media_id)
        where = and_(*where_clauses)

        if action == "featured":
            db.execute(event_media.update().where(where).values(featured=True))
        elif action == "unfeatured":
            db.execute(event_media.update().where(where).values(featured=False))
        elif action == "approved":
            db.execute(event_media.update().where(where).values(
                status="approved",
                approved_at=datetime.utcnow(),
                approved_by_user_id=user_id,
                processed_at=datetime.utcnow(),
            ))
        elif action == "skipped":
            db.execute(event_media.update().where(where).values(
                status="skipped",
                skipped_by_user_id=user_id,
                processed_at=datetime.utcnow(),
            ))
        elif action == "published":
            db.execute(event_media.update().where(where).values(
                status="published",
                published_at=datetime.utcnow(),
                processed_at=datetime.utcnow(),
            ))

        # Audit
        for eid in event_ids:
            try:
                db.add(EventEdit(
                    event_id=eid,
                    field_name=f"bulk_action:{action}" + (f":{media_id}" if media_id else ""),
                    old_value=None, new_value=action,
                    source="manual", user_id=user_id,
                ))
            except Exception:
                pass

        return jsonify({
            "ok": True,
            "action": action,
            "affected_events": len(event_ids),
            "media_id": media_id,
        })


@app.route("/api/event/batch-approve", methods=["POST"])
@auth_required
def batch_approve():
    with get_db() as db:
        data = get_json_or_400()
        event_ids = data.get("event_ids", [])
        media_id = data.get("media_id", "")
        featured = data.get("featured", False)
        priority = data.get("priority", 0)

        approved = 0
        for eid in event_ids:
            where = and_(
                event_media.c.event_id == eid,
                event_media.c.status == "new"
            )
            if media_id:
                where = and_(where, event_media.c.media_id == media_id)

            result = db.execute(
                event_media.update()
                .where(where)
                .values(
                    status="approved",
                    featured=featured,
                    priority=priority,
                    approved_at=datetime.utcnow()
                )
            )
            approved += result.rowcount

        return jsonify({"ok": True, "approved": approved})


# ============================================================
# DRUPAL INTEGRACIJA API
# ============================================================

@app.route("/api/drupal/<media_id>/queue")
@auth_required
def drupal_queue(media_id):
    with get_db() as db:
        limit = int(request.args.get("limit", 20))
        offset = int(request.args.get("offset", 0))

        rows = db.execute(
            event_media.select().where(
                and_(
                    event_media.c.media_id == media_id,
                    event_media.c.status.in_(["approved", "queued"])
                )
            )
        ).fetchall()

        event_ids = [r.event_id for r in rows]
        if not event_ids:
            return jsonify({"media_id": media_id, "count": 0, "events": []})

        events = db.query(Event).filter(
            Event.id.in_(event_ids),
            Event.date_start >= date.today()
        ).order_by(Event.date_start.asc()).offset(offset).limit(limit).all()

        for event in events:
            db.execute(
                event_media.update()
                .where(and_(
                    event_media.c.event_id == event.id,
                    event_media.c.media_id == media_id,
                    event_media.c.status == "approved"
                ))
                .values(status="queued")
            )

        return jsonify({
            "media_id": media_id,
            "count": len(events),
            "total_queued": len(event_ids),
            "events": [event.to_drupal(media_id) for event in events]
        })


@app.route("/api/drupal/<media_id>/push", methods=["POST"])
@auth_required
def drupal_push_confirm(media_id):
    with get_db() as db:
        data = get_json_or_400()
        scraper_id = data.get("scraper_id")
        drupal_nid = data.get("drupal_nid")
        drupal_status = data.get("status", "published")

        if not scraper_id or not drupal_nid:
            return jsonify({"error": "scraper_id in drupal_nid sta obvezna"}), 400

        db.execute(
            event_media.update()
            .where(and_(
                event_media.c.event_id == scraper_id,
                event_media.c.media_id == media_id
            ))
            .values(
                status="pushed",
                drupal_nid=drupal_nid,
                drupal_status=drupal_status,
                pushed_at=datetime.utcnow()
            )
        )

        log = DrupalPushLog(
            event_id=scraper_id,
            media_id=media_id,
            drupal_nid=drupal_nid,
            action="create",
            status="success",
        )
        db.add(log)

        return jsonify({"ok": True, "drupal_nid": drupal_nid})


@app.route("/api/drupal/<media_id>/confirm", methods=["POST"])
@auth_required
def drupal_publish_confirm(media_id):
    with get_db() as db:
        data = get_json_or_400()
        scraper_id = data.get("scraper_id")

        db.execute(
            event_media.update()
            .where(and_(
                event_media.c.event_id == scraper_id,
                event_media.c.media_id == media_id
            ))
            .values(
                status="published",
                drupal_status="published",
                published_at=datetime.utcnow()
            )
        )
        return jsonify({"ok": True})


@app.route("/api/drupal/<media_id>/export")
@auth_required
def drupal_export(media_id):
    with get_db() as db:
        status_filter = request.args.get("status", "approved")
        date_from = request.args.get("from", date.today().isoformat())
        date_to = request.args.get("to", (date.today() + timedelta(days=60)).isoformat())
        output_format = request.args.get("format", "json")

        rows = db.execute(
            event_media.select().where(
                and_(
                    event_media.c.media_id == media_id,
                    event_media.c.status == status_filter
                )
            )
        ).fetchall()

        event_ids = [r.event_id for r in rows]
        events = db.query(Event).filter(
            Event.id.in_(event_ids),
            Event.date_start >= date.fromisoformat(date_from),
            Event.date_start <= date.fromisoformat(date_to),
        ).order_by(Event.date_start.asc()).all()

        if output_format == "csv":
            import csv
            import io
            from flask import Response
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow([
                "title", "body", "field_prizorisce", "field_vrsta_dogodka",
                "field_termin_start", "field_termin_end",
                "field_slika", "field_organizator", "field_cena",
                "field_izpostavi", "field_vir_url"
            ])
            for event in events:
                drupal = event.to_drupal(media_id)
                writer.writerow([
                    drupal["title"],
                    drupal["body"]["value"],
                    drupal["field_prizorisce"],
                    drupal["field_vrsta_dogodka"],
                    drupal["field_termin"]["value"] or "",
                    drupal["field_termin"]["end_value"] or "",
                    drupal["field_slika"],
                    drupal["field_organizator"],
                    drupal["field_cena"],
                    "1" if drupal["field_izpostavi"] else "0",
                    drupal["field_vir_url"],
                ])
            return Response(
                output.getvalue(),
                mimetype="text/csv",
                headers={"Content-Disposition": f"attachment;filename={media_id}_events.csv"}
            )

        return jsonify({
            "media_id": media_id,
            "count": len(events),
            "exported_at": datetime.utcnow().isoformat(),
            "events": [event.to_drupal(media_id) for event in events]
        })


# ============================================================
# PODATKOVNI API
# ============================================================

@app.route("/api/event/<int:event_id>")
@auth_required
def get_event(event_id):
    with get_db() as db:
        event = db.query(Event).get(event_id)
        if not event:
            return jsonify({"error": "Dogodek ni najden"}), 404

        data = event.to_dict()
        data["portals"] = {}
        rows = db.execute(
            event_media.select().where(event_media.c.event_id == event_id)
        ).fetchall()
        for row in rows:
            data["portals"][row.media_id] = {
                "status": row.status,
                "featured": bool(row.featured) if row.featured else False,
                "priority": row.priority or 0,
                "drupal_nid": row.drupal_nid,
                "editor_notes": row.editor_notes,
            }
        return jsonify(data)


@app.route("/api/event/<int:event_id>/drupal-json")
@auth_required
def get_drupal_json(event_id):
    with get_db() as db:
        event = db.query(Event).get(event_id)
        if not event:
            return jsonify({"error": "Dogodek ni najden"}), 404
        media_id = request.args.get("media", None)
        return jsonify(event.to_drupal(media_id))


@app.route("/api/event/<int:event_id>/copy-text")
@auth_required
def get_copy_text(event_id):
    with get_db() as db:
        event = db.query(Event).get(event_id)
        if not event:
            return jsonify({"error": "Dogodek ni najden"}), 404

        lines = [event.title or "", ""]
        if event.date_start:
            date_str = event.date_start.strftime("%d. %m. %Y")
            if event.date_end and event.date_end != event.date_start:
                date_str += f" – {event.date_end.strftime('%d. %m. %Y')}"
            if event.time_start:
                date_str += f", {event.time_start}"
                if event.time_end:
                    date_str += f"–{event.time_end}"
            lines.append(f"Datum: {date_str}")
        if event.location:
            lines.append(f"Lokacija: {event.location}")
        if event.price:
            lines.append(f"Vstopnina: {event.price}")
        if event.organizer:
            lines.append(f"Organizator: {event.organizer}")
        lines.append("")
        if event.description:
            lines.append(event.description)
        if event.source_url:
            lines.extend(["", f"Več info: {event.source_url}"])

        return jsonify({
            "text": "\n".join(lines),
            "image_url": event.image_url or "",
        })


# ============================================================
# STATISTIKA
# ============================================================

@app.route("/api/stats")
@auth_required
def stats():
    with get_db() as db:
        today = date.today()
        total_events = db.query(Event).count()
        future_events = db.query(Event).filter(Event.date_start >= today).count()

        portal_stats = {}
        for media in db.query(MediaOutlet).all():
            statuses = db.execute(
                event_media.select().where(event_media.c.media_id == media.id)
            ).fetchall()
            portal_stats[media.id] = {
                "name": media.name,
                "total": len(statuses),
                "new": sum(1 for s in statuses if s.status == "new"),
                "approved": sum(1 for s in statuses if s.status == "approved"),
                "published": sum(1 for s in statuses if s.status == "published"),
                "skipped": sum(1 for s in statuses if s.status == "skipped"),
            }

        region_stats = db.query(
            Event.region, func.count(Event.id)
        ).filter(Event.date_start >= today).group_by(Event.region).all()

        source_stats = db.query(
            Event.source_id, func.count(Event.id)
        ).filter(Event.date_start >= today).group_by(Event.source_id).order_by(
            func.count(Event.id).desc()
        ).all()

        logs = db.query(ScrapeLog).order_by(
            ScrapeLog.started_at.desc()
        ).limit(20).all()

        return jsonify({
            "total_events": total_events,
            "future_events": future_events,
            "portals": portal_stats,
            "by_region": {r: c for r, c in region_stats if r},
            "by_source": {s: c for s, c in source_stats},
            "recent_scrapes": [{
                "source_id": log.source_id,
                "started_at": log.started_at.isoformat() if log.started_at else None,
                "events_found": log.events_found,
                "events_new": log.events_new,
                "status": log.status,
            } for log in logs],
        })


@app.route("/uporabniki")
@admin_required
def users_page():
    """Stran za upravljanje uporabnikov (samo admin)."""
    return render_template("users.html")


# === UPORABNIKI API ===

def _save_auth_yaml():
    """Shrani trenutni AUTH_USERS dict nazaj v auth.yaml."""
    with open(auth_config_path, "w", encoding="utf-8") as f:
        yaml.dump(auth_config, f, default_flow_style=False, allow_unicode=True)


@app.route("/api/users")
@admin_required
def list_users():
    """Vrne seznam vseh uporabnikov (UNION DB + auth.yaml)."""
    import json as _json
    out = []
    seen_emails = set()
    with get_db() as db:
        # Primarno: vsi DB uporabniki
        for u in db.query(User).filter(User.is_active == True).all():  # noqa
            email = u.email.lower()
            allowed = []
            if u.allowed_media:
                try:
                    allowed = _json.loads(u.allowed_media)
                except Exception:
                    allowed = []
            out.append({
                "email": email,
                "name": u.name or email,
                "role": u.role,
                "allowed_media": allowed,
                "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
                "created_at": u.created_at.isoformat() if u.created_at else None,
                "in_db": True,
                "has_password": bool(u.password_hash),
            })
            seen_emails.add(email)

        # Dodaj tudi auth.yaml uporabnike, ki še niso v DB
        for email, u in AUTH_USERS.items():
            if email.lower() in seen_emails:
                continue
            out.append({
                "email": email,
                "name": u.get("name", email),
                "role": "admin",
                "allowed_media": [],
                "last_login_at": None,
                "created_at": None,
                "in_db": False,
                "has_password": True,
            })

        media_list = [{"id": m.id, "name": m.name} for m in db.query(MediaOutlet).all()]
    return jsonify({"users": out, "media_outlets": media_list})


@app.route("/api/users", methods=["POST"])
@admin_required
def create_user():
    """Ustvari novega uporabnika (shranjen v DB za persistenco na Render)."""
    import json as _json
    data = get_json_or_400()
    email = (data.get("email") or "").lower().strip()
    name = (data.get("name") or email).strip()
    password = data.get("password") or ""
    role = data.get("role", "editor")
    allowed_media = data.get("allowed_media") or []

    if not email or "@" not in email:
        abort(400, description="Veljavni email je obvezen")
    if not password or len(password) < 6:
        abort(400, description="Geslo mora imeti najmanj 6 znakov")
    if role not in ("admin", "editor"):
        abort(400, description="Role mora biti 'admin' ali 'editor'")

    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    with get_db() as db:
        existing = db.query(User).filter(User.email == email).first()
        if existing and existing.is_active and existing.password_hash:
            abort(400, description="Uporabnik s tem emailom že obstaja")
        if existing:
            # Reaktiviraj
            existing.name = name
            existing.role = role
            existing.is_active = True
            existing.password_hash = pw_hash
            existing.allowed_media = _json.dumps(allowed_media) if allowed_media else None
        else:
            u = User(email=email, name=name, role=role, is_active=True,
                     password_hash=pw_hash,
                     allowed_media=_json.dumps(allowed_media) if allowed_media else None,
                     created_at=datetime.utcnow())
            db.add(u)

    # Sync v in-memory cache za login (po naslednjem login-u DB se zaobide)
    AUTH_USERS[email] = {"name": name, "password_hash": pw_hash}

    return jsonify({"ok": True, "email": email})


@app.route("/api/users/<email>", methods=["PATCH"])
@admin_required
def update_user(email):
    """Posodobi uporabnika (ime, role, allowed_media, geslo)."""
    import json as _json
    data = get_json_or_400()
    email = email.lower().strip()

    with get_db() as db:
        u = db.query(User).filter(User.email == email).first()
        # Če ne obstaja v DB, preveri auth.yaml (legacy admin)
        if u is None:
            if email not in (e.lower() for e in AUTH_USERS):
                abort(404, description="Uporabnik ne obstaja")
            u = User(email=email, name=AUTH_USERS[email]["name"], role="admin",
                     is_active=True,
                     password_hash=AUTH_USERS[email].get("password_hash"),
                     created_at=datetime.utcnow())
            db.add(u)
            db.flush()

        if "name" in data:
            u.name = data["name"]
        if "password" in data and data["password"]:
            if len(data["password"]) < 6:
                abort(400, description="Geslo mora imeti najmanj 6 znakov")
            new_hash = bcrypt.hashpw(data["password"].encode(), bcrypt.gensalt()).decode()
            u.password_hash = new_hash
            # Sync v in-memory cache
            AUTH_USERS[email] = {"name": u.name, "password_hash": new_hash}
        if "role" in data:
            if data["role"] not in ("admin", "editor"):
                abort(400, description="Role mora biti 'admin' ali 'editor'")
            u.role = data["role"]
        if "allowed_media" in data:
            allowed = data["allowed_media"] or []
            u.allowed_media = _json.dumps(allowed) if allowed else None
        if "is_active" in data:
            u.is_active = bool(data["is_active"])

    return jsonify({"ok": True, "email": email})


@app.route("/api/users/<email>", methods=["DELETE"])
@admin_required
def delete_user(email):
    """Pobriši uporabnika (deaktiviraj v DB + odstrani iz auth.yaml)."""
    email = email.lower().strip()
    me = (session.get("user_email") or "").lower()
    if email == me:
        abort(400, description="Ne moreš pobrisati samega sebe")

    with get_db() as db:
        u = db.query(User).filter(User.email == email).first()
        if not u and email not in (e.lower() for e in AUTH_USERS):
            abort(404)
        if u:
            u.is_active = False
            u.password_hash = None  # ne more se več prijaviti

    AUTH_USERS.pop(email, None)
    return jsonify({"ok": True})


@app.route("/healthz")
def healthz():
    """Lahkoten health endpoint za Render (brez auth, brez DB query)."""
    return "ok", 200


@app.route("/health")
@auth_required
def health_page():
    """HTML pregled zdravja virov in sistemskih metrik."""
    return render_template("health.html")


@app.route("/api/metrics")
@auth_required
def system_metrics():
    """Sistemske metrike za observability (events, scrape, source health)."""
    from scraper.observability import collect_system_metrics
    return jsonify({
        "metrics": collect_system_metrics(),
        "database": database_info(),
    })


@app.route("/api/health")
@auth_required
def source_health():
    with get_db() as db:
        healths = db.query(SourceHealth).all()
        unprocessed = db.query(UnprocessedUrl).filter(
            UnprocessedUrl.status == "pending"
        ).all()

        return jsonify({
            "sources": [{
                "id": h.source_id,
                "name": h.source_name,
                "parser_type": h.parser_type,
                "status": h.status,
                "last_check": h.last_check.isoformat() if h.last_check else None,
                "last_success": h.last_success.isoformat() if h.last_success else None,
                "last_events_found": h.last_events_found or 0,
                "consecutive_errors": h.consecutive_errors or 0,
                "consecutive_successes": h.consecutive_successes or 0,
                "avg_duration_ms": h.avg_duration_ms or 0,
                "url": h.feed_url or h.list_url,
                "last_error": h.last_error_msg[:200] if h.last_error_msg else None,
            } for h in healths],
            "unprocessed_urls": [{
                "source_id": u.source_id,
                "url": u.url,
                "reason": u.reason,
            } for u in unprocessed],
        })


# ============================================================
# RUČNI SCRAPING & ENRICHMENT (on-demand)
# ============================================================

# Globalno stanje opravil
_TASK_STATE = {
    "scrape": {
        "running": False,
        "started_at": None,
        "result": None,
        "error": None,
        "progress": {},
        "cancel_event": None,  # threading.Event za prekinitev
    },
}


def _run_scrape_task(days_ahead, media_id=None):
    """Sproži scraping virov v ozadju.
    Če je media_id podan, scrapaš samo vire iz regij tega medija."""
    import threading
    import uuid

    cancel_event = threading.Event()
    session_id = str(uuid.uuid4())
    progress = {"phase": "starting", "percent": 0}
    _TASK_STATE["scrape"] = {
        "running": True,
        "started_at": datetime.utcnow().isoformat(),
        "result": None,
        "error": None,
        "days_ahead": days_ahead,
        "media_id": media_id,
        "session_id": session_id,
        "progress": progress,
        "cancel_event": cancel_event,
    }

    def _job():
        try:
            from scraper.engine import ScraperEngine
            engine = ScraperEngine()
            engine.days_ahead = days_ahead
            results = engine.run_all(
                progress=progress, media_id=media_id,
                cancel_event=cancel_event, session_id=session_id,
            )
            cancelled = results.pop("_cancelled", False)
            cancelled_at_index = results.pop("_cancelled_at_index", None)
            total_new = sum(r.get("new", 0) for r in results.values()
                            if isinstance(r, dict) and "error" not in r)
            total_updated = sum(r.get("updated", 0) for r in results.values()
                                 if isinstance(r, dict) and "error" not in r)
            total_stale = sum(r.get("stale", 0) for r in results.values()
                              if isinstance(r, dict) and "error" not in r)
            errors = {sid: r["error"] for sid, r in results.items()
                      if isinstance(r, dict) and "error" in r}
            finished_at = datetime.utcnow()
            started = datetime.fromisoformat(_TASK_STATE["scrape"]["started_at"])
            duration_s = int((finished_at - started).total_seconds())
            result_summary = {
                "total_new": total_new,
                "total_updated": total_updated,
                "total_stale": total_stale,
                "sources_ok": sum(1 for r in results.values()
                                  if isinstance(r, dict) and "error" not in r),
                "sources_err": len(errors),
                "errors": errors,
                "duration_s": duration_s,
                "cancelled": cancelled,
                "cancelled_at_index": cancelled_at_index,
            }
            _TASK_STATE["scrape"].update({
                "running": False,
                "finished_at": finished_at.isoformat(),
                "duration_s": duration_s,
                "cancelled": cancelled,
                "result": result_summary,
            })
            # Webhook notifikacija (samo če uspešen, ne prekinjen)
            if not cancelled:
                try:
                    from scraper.notifications import notify_scrape_complete
                    notify_scrape_complete(result_summary)
                except Exception as we:
                    print(f"[WEBHOOK] {we}", flush=True)
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f"[SCRAPE THREAD ERROR] {e}\n{tb}", flush=True)
            _TASK_STATE["scrape"]["running"] = False
            _TASK_STATE["scrape"]["error"] = str(e)

    t = threading.Thread(target=_job, daemon=True)
    t.start()


@app.route("/api/scrape/refresh", methods=["POST"])
@auth_required
def trigger_scrape():
    """Sproži ročno scrapanje vseh virov.
    Query/JSON parameter: days = 30|60|90|120 (privzeto 30)."""
    data = request.get_json(silent=True) or {}
    days = int(data.get("days") or request.args.get("days") or 30)
    if days not in (7, 14, 30, 60, 90):
        days = 30
    media_id = data.get("media") or request.args.get("media") or None

    if _TASK_STATE["scrape"]["running"]:
        return jsonify({"ok": False, "error": "Scraping že teče.", "state": _TASK_STATE["scrape"]}), 409

    _run_scrape_task(days, media_id=media_id)
    return jsonify({"ok": True, "started": True, "days_ahead": days, "media_id": media_id})


@app.route("/api/dashboard/snapshot")
@auth_required
def dashboard_snapshot():
    """AJAX endpoint za osvežitev dashboard-a brez polnega reload-a.

    Vrne lažji JSON: posodobljen seznam dogodkov + header podatke.
    Frontend kliče po koncu scrape-a in pri spremembah filtrov.
    """
    today = date.today()
    media_id = request.args.get("media", "")
    status = request.args.get("status", "new")
    search = request.args.get("q", "")
    event_type = request.args.get("type", "")
    region = request.args.get("region", "")
    show_inactive = request.args.get("show_inactive") in ("1", "true")

    # Datumi
    try:
        df_raw = request.args.get("from")
        if not df_raw or date.fromisoformat(df_raw) < today:
            date_from = today.isoformat()
        else:
            date_from = df_raw
    except ValueError:
        date_from = today.isoformat()
    try:
        dt_raw = request.args.get("to")
        df = date.fromisoformat(date_from)
        if not dt_raw or date.fromisoformat(dt_raw) < df:
            date_to = (df + timedelta(days=30)).isoformat()
        else:
            date_to = dt_raw
    except ValueError:
        date_to = (date.fromisoformat(date_from) + timedelta(days=30)).isoformat()

    page_num = int(request.args.get("p", 1))
    per_page = int(request.args.get("per_page", 30))

    with get_db() as db:
        query = db.query(Event).filter(
            Event.date_start >= date.fromisoformat(date_from),
            Event.date_start <= date.fromisoformat(date_to),
        )
        if not show_inactive:
            query = query.filter(Event.is_active == True)  # noqa: E712

        if media_id:
            query = query.join(event_media, event_media.c.event_id == Event.id).filter(
                event_media.c.media_id == media_id
            )
            if status and status != "all":
                query = query.filter(event_media.c.status == status)
        elif status and status != "all":
            from sqlalchemy import exists
            query = query.filter(exists().where(and_(
                event_media.c.event_id == Event.id,
                event_media.c.status == status,
            )))

        if event_type:
            query = query.filter(Event.event_type == event_type)
        if region:
            query = query.filter(Event.region == region)
        if search:
            like = f"%{search}%"
            query = query.filter(
                Event.title.ilike(like) | Event.description.ilike(like) |
                Event.location.ilike(like) | Event.organizer.ilike(like)
            )

        total = query.count()
        events = query.order_by(Event.date_start.asc()).offset(
            (page_num - 1) * per_page
        ).limit(per_page).all()

        last_scrape = db.query(ScrapeLog).filter(
            ScrapeLog.finished_at != None  # noqa: E711
        ).order_by(ScrapeLog.finished_at.desc()).first()

        last_scrape_iso = None
        if last_scrape and last_scrape.finished_at:
            try:
                from zoneinfo import ZoneInfo
                last_scrape_iso = last_scrape.finished_at.replace(
                    tzinfo=ZoneInfo("UTC")
                ).astimezone(ZoneInfo("Europe/Ljubljana")).isoformat()
            except Exception:
                last_scrape_iso = (last_scrape.finished_at + timedelta(hours=2)).isoformat()

        total_active = db.query(Event).filter(
            Event.date_start >= today, Event.is_active == True  # noqa: E712
        ).count()

        return jsonify({
            "events": [e.to_dict() for e in events],
            "total_events": total,
            "total_active": total_active,
            "page": page_num,
            "per_page": per_page,
            "total_pages": (total + per_page - 1) // per_page,
            "last_scrape_at": last_scrape_iso,
        })


@app.route("/api/enrichment/run", methods=["POST"])
@auth_required
def trigger_enrichment():
    """Naknadno dopolni manjkajoče opise in slike za obstoječe dogodke.

    Body: {
      "scope": "missing_desc" | "missing_image" | "both",
      "limit": 100,
      "media_id": "mariborinfo"  (opcijsko: samo dogodki tega medija)
    }
    Teče v ozadju (thread). Status preko /api/tasks/status.
    """
    import threading
    data = get_json_or_400() if request.is_json else (request.get_json(silent=True) or {})
    scope = data.get("scope", "both")
    limit = int(data.get("limit", 200))
    media_id = data.get("media_id") or None

    if _TASK_STATE["scrape"].get("running"):
        return jsonify({"ok": False, "error": "Scraping že teče. Počakaj da konča."}), 409

    progress = {"phase": "enrichment_only", "percent": 0,
                "enrich_phase": None, "enrich_index": 0, "enrich_total": 0}
    _TASK_STATE["scrape"] = {
        "running": True,
        "started_at": datetime.utcnow().isoformat(),
        "result": None, "error": None,
        "progress": progress,
        "cancel_event": None,
        "is_enrichment_only": True,
    }

    def _job():
        try:
            from scraper.image_fallback import (
                fill_missing_descriptions, fill_missing_images,
            )
            from sqlalchemy import or_ as _or
            with get_db() as db:
                # Določi event_ids glede na scope
                from datetime import date as _d
                base_q = db.query(Event).filter(
                    Event.date_start >= _d.today(),
                    Event.is_active == True,  # noqa
                )
                if media_id:
                    base_q = base_q.join(event_media, event_media.c.event_id == Event.id)\
                                    .filter(event_media.c.media_id == media_id)

                ids_desc = []
                ids_img = []
                if scope in ("missing_desc", "both"):
                    ids_desc = [e.id for e in base_q.filter(
                        _or(Event.description == None, Event.description == "")  # noqa
                    ).limit(limit).all()]
                if scope in ("missing_image", "both"):
                    ids_img = [e.id for e in base_q.filter(
                        _or(Event.image_url == None, Event.image_url == "")  # noqa
                    ).limit(limit).all()]

            if ids_desc:
                with get_db() as db:
                    fill_missing_descriptions(
                        db, event_ids=ids_desc, max_seconds=300,
                        progress=progress, percent_range=(0, 50),
                    )
            if ids_img:
                with get_db() as db:
                    fill_missing_images(
                        db, event_ids=ids_img, max_seconds=300,
                        progress=progress, percent_range=(50, 100),
                    )

            progress["percent"] = 100
            duration = int((datetime.utcnow() - datetime.fromisoformat(
                _TASK_STATE["scrape"]["started_at"])).total_seconds())
            _TASK_STATE["scrape"].update({
                "running": False,
                "finished_at": datetime.utcnow().isoformat(),
                "duration_s": duration,
                "result": {
                    "is_enrichment": True,
                    "desc_processed": len(ids_desc),
                    "img_processed": len(ids_img),
                    "duration_s": duration,
                },
            })
        except Exception as e:
            import traceback
            print(f"[ENRICHMENT] {e}\n{traceback.format_exc()}", flush=True)
            _TASK_STATE["scrape"]["running"] = False
            _TASK_STATE["scrape"]["error"] = str(e)

    threading.Thread(target=_job, daemon=True).start()
    return jsonify({"ok": True, "started": True, "scope": scope, "media_id": media_id})


@app.route("/api/published-check/debug")
@auth_required
def debug_published_check():
    """Diagnostika: kaj točno Render vidi za določen portal.
    Uporabi: /api/published-check/debug?media=ptujinfo
    """
    from scraper.published_checker import PublishedChecker, PORTAL_CALENDARS
    from scraper.dedup import normalize_text, check_against_published

    media_id = request.args.get("media", "ptujinfo")
    portal_url = PORTAL_CALENDARS.get(media_id)

    out = {
        "media_id": media_id,
        "portal_url": portal_url,
        "fetch_ok": False,
        "events_found": 0,
        "first_events": [],
        "our_new_events_for_media": 0,
        "matches_in_db": 0,
        "first_match_examples": [],
        "no_match_examples": [],
        "raw_fetch_status": None,
    }

    if not portal_url:
        out["error"] = f"PORTAL_CALENDARS nima vnosa za '{media_id}'"
        return jsonify(out)

    # 1. Test fetch z istim sessionom kot PublishedChecker (cloudscraper)
    try:
        pc_test = PublishedChecker(max_pages=1)
        resp = pc_test.session.get(portal_url, timeout=20)
        out["raw_fetch_status"] = resp.status_code
        out["raw_response_size"] = len(resp.text)
        out["uses_cloudscraper"] = "cloudscraper" in str(type(pc_test.session)).lower()
    except Exception as e:
        out["error"] = f"Fetch napaka: {e}"
        return jsonify(out)

    # 2. Test parser
    try:
        pc = PublishedChecker(max_pages=5)
        published = pc.fetch_published_events(media_id)
        out["fetch_ok"] = True
        out["events_found"] = len(published)
        out["first_events"] = [
            {"title": p["title"], "date_start": p["date_start"].isoformat()}
            for p in published[:10]
        ]
    except Exception as e:
        out["error"] = f"Parser napaka: {e}"
        return jsonify(out)

    # 3. Test match z našo bazo
    with get_db() as db:
        rows = db.execute(
            event_media.select().where(and_(
                event_media.c.media_id == media_id,
                event_media.c.status == "new",
            ))
        ).fetchall()
        out["our_new_events_for_media"] = len(rows)

        for row in rows:
            ev = db.query(Event).get(row.event_id)
            if not ev or not ev.date_start:
                continue
            matched = check_against_published(ev.title, ev.date_start, published)
            if matched:
                out["matches_in_db"] += 1
                if len(out["first_match_examples"]) < 5:
                    out["first_match_examples"].append({
                        "id": ev.id,
                        "title": ev.title,
                        "date": ev.date_start.isoformat(),
                    })
            elif len(out["no_match_examples"]) < 5:
                out["no_match_examples"].append({
                    "id": ev.id,
                    "title": ev.title,
                    "date": ev.date_start.isoformat(),
                })

    return jsonify(out)


@app.route("/api/published-check/run", methods=["POST"])
@auth_required
def run_published_check():
    """Naknadno preveri katere nove dogodke smo morda že imeli na svojih portalih
    in jih označi z status='published' (izgine iz "Novi" filtra).

    Body (vse opcijsko): {"media_id": "mariborinfo", "include_approved": false}
    """
    import threading
    data = request.get_json(silent=True) or {}
    media_id_filter = data.get("media_id") or None
    include_approved = bool(data.get("include_approved", False))

    if _TASK_STATE["scrape"].get("running"):
        return jsonify({"ok": False, "error": "Drugo opravilo že teče."}), 409

    progress = {"phase": "published_check", "percent": 0, "checked": 0, "marked": 0}
    _TASK_STATE["scrape"] = {
        "running": True,
        "started_at": datetime.utcnow().isoformat(),
        "result": None, "error": None,
        "progress": progress,
        "is_published_check": True,
    }

    def _job():
        try:
            from scraper.published_checker import PublishedChecker, PORTAL_CALENDARS
            from scraper.dedup import check_against_published
            checker = PublishedChecker(max_pages=5)
            checker.reset_cache(clear_global=True)  # ročni klic = sveža poizvedba

            media_ids = [media_id_filter] if media_id_filter else list(PORTAL_CALENDARS.keys())

            total_checked = 0
            total_marked = 0
            portals_unreachable = 0
            portals_with_events = 0

            for idx, mid in enumerate(media_ids, 1):
                progress["percent"] = int(100 * (idx - 1) / max(len(media_ids), 1))
                progress["current_media"] = mid

                published = checker.fetch_published_events(mid)
                if not published:
                    portals_unreachable += 1
                    continue
                portals_with_events += 1

                with get_db() as db:
                    # Najdi dogodke s status="new" (in/ali "approved") za ta medij
                    statuses = ["new"] + (["approved"] if include_approved else [])
                    rows = db.execute(
                        event_media.select().where(and_(
                            event_media.c.media_id == mid,
                            event_media.c.status.in_(statuses),
                        ))
                    ).fetchall()

                    for row in rows:
                        ev = db.query(Event).get(row.event_id)
                        if not ev or not ev.date_start:
                            continue
                        total_checked += 1
                        if check_against_published(ev.title, ev.date_start, published):
                            db.execute(
                                event_media.update().where(and_(
                                    event_media.c.event_id == ev.id,
                                    event_media.c.media_id == mid,
                                )).values(status="published",
                                          published_at=datetime.utcnow(),
                                          processed_at=datetime.utcnow())
                            )
                            db.add(EventEdit(
                                event_id=ev.id,
                                field_name=f"em_status:{mid}",
                                old_value="new", new_value="published",
                                source="auto-published-check", user_id=None,
                            ))
                            total_marked += 1
                            progress["marked"] = total_marked
                        progress["checked"] = total_checked

            progress["percent"] = 100
            duration = int((datetime.utcnow() - datetime.fromisoformat(
                _TASK_STATE["scrape"]["started_at"])).total_seconds())
            _TASK_STATE["scrape"].update({
                "running": False,
                "finished_at": datetime.utcnow().isoformat(),
                "duration_s": duration,
                "result": {
                    "is_published_check": True,
                    "checked": total_checked,
                    "marked": total_marked,
                    "media_count": len(media_ids),
                    "portals_unreachable": portals_unreachable,
                    "portals_with_events": portals_with_events,
                    "warning": (
                        "Portali niso dostopni z Render IP-jev (verjetno Cloudflare 403). "
                        "Kontaktiraj netmedia admina za whitelist. Glej DEPLOYMENT.md."
                        if portals_with_events == 0 and portals_unreachable > 0
                        else None
                    ),
                    "duration_s": duration,
                },
            })
        except Exception as e:
            import traceback
            print(f"[PUB-CHECK] {e}\n{traceback.format_exc()}", flush=True)
            _TASK_STATE["scrape"]["running"] = False
            _TASK_STATE["scrape"]["error"] = str(e)

    threading.Thread(target=_job, daemon=True).start()
    return jsonify({"ok": True, "started": True, "media_id": media_id_filter})


@app.route("/api/scrape/latest-summary")
@auth_required
def latest_scrape_summary():
    """Vrne povzetek zadnje dokončane scrape session-e.

    Uporablja session_id (UUID) za natančno grupiranje — vsi logi enega
    /api/scrape/refresh klica imajo isti session_id. Tako se različni klici
    NIKOLI ne mešajo, tudi če sledijo zaporedoma.

    Fallback: če session_id manjka (legacy logi pred Phase 2.1), uporabimo
    5-min gap detection.
    """
    with get_db() as db:
        last = db.query(ScrapeLog).filter(
            ScrapeLog.finished_at != None,  # noqa
            ScrapeLog.status.in_(("success", "skipped")),
        ).order_by(ScrapeLog.finished_at.desc()).first()

        if not last:
            return jsonify({"has_summary": False})

        # Primarno: grupiraj po session_id
        if last.session_id:
            session_logs = db.query(ScrapeLog).filter(
                ScrapeLog.session_id == last.session_id,
            ).all()
        else:
            # Fallback za stare loge (5-min gap)
            recent_all = db.query(ScrapeLog).filter(
                ScrapeLog.started_at >= last.finished_at - timedelta(hours=2),
                ScrapeLog.started_at <= last.finished_at,
                ScrapeLog.session_id == None,  # noqa
            ).order_by(ScrapeLog.started_at.desc()).all()
            session_logs = [last]
            prev = last.started_at
            for log in recent_all:
                if log.id == last.id:
                    continue
                if not log.started_at:
                    continue
                gap = (prev - log.started_at).total_seconds()
                if gap > 300:
                    break
                session_logs.append(log)
                prev = log.started_at

        total_new = sum(l.events_new or 0 for l in session_logs)
        total_updated = sum(l.events_updated or 0 for l in session_logs)
        total_stale = sum(l.events_marked_stale or 0 for l in session_logs)
        total_dup = sum(l.events_duplicate or 0 for l in session_logs)
        ok_count = sum(1 for l in session_logs if l.status == "success")
        err_count = sum(1 for l in session_logs if l.status == "error")
        first_started = min((l.started_at for l in session_logs if l.started_at), default=last.started_at)
        duration_s = int((last.finished_at - first_started).total_seconds())

        # Pretvori v lokalni čas
        try:
            from zoneinfo import ZoneInfo
            finished_local = last.finished_at.replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo("Europe/Ljubljana"))
        except Exception:
            finished_local = last.finished_at + timedelta(hours=2)

        # Ali je uporabnik že videl?
        user_id = current_user_id(db)
        is_unseen = False
        if user_id:
            user = db.query(User).get(user_id)
            if user:
                seen_at = user.last_scrape_seen_at
                is_unseen = (seen_at is None) or (last.finished_at > seen_at)

        return jsonify({
            "has_summary": True,
            "is_unseen": is_unseen,
            "finished_at": finished_local.isoformat(),
            "duration_s": duration_s,
            "sources_ok": ok_count,
            "sources_err": err_count,
            "total_new": total_new,
            "total_updated": total_updated,
            "total_stale": total_stale,
            "total_duplicate": total_dup,
        })


@app.route("/api/scrape/mark-summary-seen", methods=["POST"])
@auth_required
def mark_summary_seen():
    """Označi zadnji scrape summary kot 'viden' za trenutnega uporabnika."""
    with get_db() as db:
        user_id = current_user_id(db)
        if user_id:
            user = db.query(User).get(user_id)
            if user:
                user.last_scrape_seen_at = datetime.utcnow()
        return jsonify({"ok": True})


@app.route("/api/scrape/cancel", methods=["POST"])
@auth_required
def cancel_scrape():
    """Prekini trenutni scrape (signaliziraj cancel_event)."""
    state = _TASK_STATE.get("scrape", {})
    if not state.get("running"):
        return jsonify({"ok": False, "error": "Ni aktivnega scrape opravila."}), 404
    cancel_event = state.get("cancel_event")
    if cancel_event is None:
        return jsonify({"ok": False, "error": "Cancel event ni na voljo."}), 500
    cancel_event.set()
    return jsonify({"ok": True, "message": "Scrape bo zaključen po trenutnem viru."})


@app.route("/api/tasks/status")
@auth_required
def task_status():
    """Stanje opravil. cancel_event (threading.Event) izpustimo — ni JSON-serializable."""
    safe_state = {}
    for key, val in _TASK_STATE.items():
        if isinstance(val, dict):
            safe_state[key] = {k: v for k, v in val.items() if k != "cancel_event"}
        else:
            safe_state[key] = val
    return jsonify(safe_state)


# ============================================================
# IZVOZ ZA DRUPAL — JSON po dogodku, zapakiran v ZIP
# ============================================================

def _slugify(text, maxlen=60):
    """Preprost slug za ime datoteke (samo a-z, 0-9, -)."""
    text = (text or "").lower()
    # zamenjava šumnikov
    for a, b in (("č", "c"), ("š", "s"), ("ž", "z"), ("đ", "d"), ("ć", "c")):
        text = text.replace(a, b)
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return (text[:maxlen].strip("-")) or "dogodek"


def event_to_export_dict(ev):
    """Pretvori Event v čist, ravni JSON slovar za uvoz v Drupal.

    Struktura je namenoma ravna in stabilna, da jo je v lastnem Drupal
    modulu enostavno mapirati na polja vsebinskega tipa.
    """
    # categories je shranjen kot niz ločen z vejico → tudi kot seznam za udobje
    cats_raw = (ev.categories or "").strip()
    cats_list = [c.strip() for c in cats_raw.split(",") if c.strip()] if cats_raw else []
    return {
        "id": ev.id,
        "title": ev.title,
        "description": ev.description,
        "date_start": ev.date_start.isoformat() if ev.date_start else None,
        "date_end": ev.date_end.isoformat() if ev.date_end else None,
        "time_start": ev.time_start,
        "time_end": ev.time_end,
        "location": ev.location,
        "address": ev.address,
        "price": ev.price,
        "organizer": ev.organizer,
        "category": ev.event_type,          # ena od 8 fiksnih kategorij
        "categories": cats_list,            # dodatne oznake (seznam)
        "target_audience": ev.target_audience,
        "district": ev.district,
        "region": ev.region,
        "image_url": ev.image_url,
        "source_url": ev.source_url,
        "detail_url": ev.detail_url,
        "ticket_url": ev.ticket_url,
        "source_id": ev.source_id,
        "source_event_id": ev.source_event_id,
        "exported_at": datetime.utcnow().isoformat() + "Z",
    }


@app.route("/api/export/drupal-zip")
@auth_required
def export_drupal_zip():
    """Prenese ZIP z eno JSON datoteko na potrjen (approved) dogodek.

    Neobvezni parameter ?status=approved|queued|pushed|published|all
    (privzeto 'approved'). Izvozi le aktivne, nepretekle dogodke.
    """
    wanted = request.args.get("status", "approved")
    with get_db() as db:
        q = db.query(Event).filter(
            Event.is_active == True,  # noqa: E712
            Event.date_start >= date.today(),
        )
        if wanted != "all":
            validate_status(wanted)
            q = q.join(event_media, event_media.c.event_id == Event.id).filter(
                event_media.c.status == wanted
            )
        events = q.order_by(Event.date_start.asc()).all()

        buf = io.BytesIO()
        seen = {}
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for ev in events:
                data = event_to_export_dict(ev)
                slug = _slugify(ev.title)
                name = f"{ev.id}-{slug}.json"
                # zaščita pred podvojenim imenom (ne bi smelo, id je unikaten)
                if name in seen:
                    name = f"{ev.id}-{slug}-{seen[name]}.json"
                seen[name] = seen.get(name, 0) + 1
                zf.writestr(
                    name,
                    json.dumps(data, ensure_ascii=False, indent=2)
                )
            # manifest z vsemi dogodki naenkrat (za paketni uvoz, če ustreza)
            zf.writestr(
                "_manifest.json",
                json.dumps(
                    {
                        "count": len(events),
                        "status": wanted,
                        "generated_at": datetime.utcnow().isoformat() + "Z",
                        "events": [event_to_export_dict(e) for e in events],
                    },
                    ensure_ascii=False, indent=2
                )
            )
        buf.seek(0)

    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    fname = f"drupal-dogodki-{wanted}-{stamp}.zip"
    return send_file(
        buf, mimetype="application/zip",
        as_attachment=True, download_name=fname
    )


if __name__ == "__main__":
    init_db()
    debug_mode = os.environ.get("FLASK_DEBUG", "0").lower() in ("1", "true", "yes")
    app.run(host="0.0.0.0", port=5000, debug=debug_mode)
