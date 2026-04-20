#!/usr/bin/env python3
"""
Bootstrap initial admin user from env vars (uporabljen ob prvem deployu).

Env vars:
  ADMIN_EMAIL      — email prvega admina
  ADMIN_PASSWORD   — začetno geslo (priporočam, da ga takoj spremeni v UI)
  ADMIN_NAME       — ime (opcijsko)

Idempotenten: če uporabnik že obstaja, ga samo posodobi na role=admin.
Tudi inicializira media outlets iz config/media.yaml.
"""

import os
import sys
import yaml
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bcrypt

from database.models import get_db, User
from scraper.bootstrap import bootstrap_media_outlets

CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")
AUTH_PATH = os.path.join(CONFIG_DIR, "auth.yaml")


def load_or_create_auth():
    if os.path.exists(AUTH_PATH):
        with open(AUTH_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {"users": []}
    return {"users": []}


def save_auth(cfg):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(AUTH_PATH, "w", encoding="utf-8") as f:
        yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True)


def main():
    print("=" * 60)
    print("Bootstrap admin user + media outlets")
    print("=" * 60)

    # 1. Bootstrap medijev (idempotenten)
    try:
        bootstrap_media_outlets()
        print("✓ Media outlets sinhronizirani")
    except Exception as e:
        print(f"⚠ Bootstrap medijev failed: {e}")

    # 2. Admin user iz env vars
    admin_email = os.environ.get("ADMIN_EMAIL", "").strip().lower()
    admin_password = os.environ.get("ADMIN_PASSWORD", "")
    admin_name = os.environ.get("ADMIN_NAME") or admin_email

    if not admin_email or not admin_password:
        print("⚠ ADMIN_EMAIL ali ADMIN_PASSWORD ni nastavljen — preskačem bootstrap admina")
        print("  (Po deployu nastavi v Render dashboard → Environment.)")
        return 0

    cfg = load_or_create_auth()
    cfg.setdefault("users", [])

    # Posodobi auth.yaml
    existing = next((u for u in cfg["users"]
                     if u.get("email", "").lower() == admin_email), None)
    pw_hash = bcrypt.hashpw(admin_password.encode(), bcrypt.gensalt()).decode()
    if existing:
        existing["password_hash"] = pw_hash
        existing["name"] = admin_name
        print(f"✓ Posodobljeno geslo za {admin_email} v auth.yaml")
    else:
        cfg["users"].append({
            "email": admin_email,
            "name": admin_name,
            "password_hash": pw_hash,
        })
        print(f"✓ Dodan admin {admin_email} v auth.yaml")

    # Auto-generate secret_key če manjka
    if not cfg.get("secret_key") or "ZAMENJAJ" in str(cfg.get("secret_key")):
        secret_from_env = os.environ.get("EVENT_SCRAPER_SECRET_KEY")
        if secret_from_env:
            cfg["secret_key"] = secret_from_env
        else:
            import secrets as _s
            cfg["secret_key"] = _s.token_hex(32)

    # Gemini API
    gemini = os.environ.get("GEMINI_API_KEY")
    if gemini:
        cfg["gemini_api_key"] = gemini

    save_auth(cfg)

    # Posodobi DB users tabelo: postavi role=admin
    with get_db() as db:
        u = db.query(User).filter(User.email == admin_email).first()
        if u is None:
            u = User(email=admin_email, name=admin_name,
                     role="admin", is_active=True,
                     created_at=datetime.utcnow())
            db.add(u)
        else:
            u.role = "admin"
            u.is_active = True
            u.name = admin_name
        print(f"✓ {admin_email} ima role=admin v DB")

    print("✓ Bootstrap končan")
    return 0


if __name__ == "__main__":
    sys.exit(main())
