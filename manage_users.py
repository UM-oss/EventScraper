#!/usr/bin/env python3
"""
Upravljanje uporabnikov za Event Scraper.

Uporaba:
  python3 manage_users.py add                  # interaktivno dodaj uporabnika
  python3 manage_users.py add -e email -p geslo -n ime
  python3 manage_users.py list                 # izpiši vse uporabnike
  python3 manage_users.py remove -e email      # odstrani uporabnika
  python3 manage_users.py reset -e email       # ponastavi geslo
"""

import os
import sys
import getpass
import argparse
import bcrypt
import yaml

CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "config", "auth.yaml"
)


def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {"users": [], "secret_key": os.urandom(32).hex()}


def save_config(config):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
    print(f"Shranjeno v {CONFIG_PATH}")


def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def cmd_add(args):
    config = load_config()
    if "users" not in config:
        config["users"] = []

    email = args.email or input("Email: ").strip()
    name = args.name or input("Ime: ").strip()
    password = args.password or getpass.getpass("Geslo: ")

    if not email or not password:
        print("Email in geslo sta obvezna!")
        sys.exit(1)

    # Preveri ali že obstaja
    for u in config["users"]:
        if u.get("email", "").lower() == email.lower():
            print(f"Uporabnik {email} že obstaja. Uporabi 'reset' za spremembo gesla.")
            sys.exit(1)

    config["users"].append({
        "email": email.lower(),
        "name": name or email,
        "password_hash": hash_password(password),
    })

    save_config(config)
    print(f"Dodan uporabnik: {email}")


def cmd_list(args):
    config = load_config()
    users = config.get("users", [])

    if not users:
        print("Ni uporabnikov.")
        return

    print(f"{'Email':35s} {'Ime':25s}")
    print("-" * 62)
    for u in users:
        print(f"{u.get('email', '?'):35s} {u.get('name', ''):25s}")
    print(f"\nSkupaj: {len(users)} uporabnikov")


def cmd_remove(args):
    config = load_config()
    email = args.email or input("Email za odstranitev: ").strip()

    original_count = len(config.get("users", []))
    config["users"] = [u for u in config.get("users", [])
                       if u.get("email", "").lower() != email.lower()]

    if len(config["users"]) < original_count:
        save_config(config)
        print(f"Odstranjen: {email}")
    else:
        print(f"Uporabnik {email} ni najden.")


def cmd_role(args):
    """Nastavi role in/ali allowed_media za uporabnika v DB.

    Primeri:
      manage_users.py role -e ana@x.si --role admin
      manage_users.py role -e bob@x.si --role editor --media mariborinfo,ptujinfo
    """
    import sys as _sys
    import json as _json
    _sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from database.models import get_db, User

    email = args.email or input("Email: ").strip()
    new_role = args.role
    if new_role and new_role not in ("admin", "editor"):
        print("Role mora biti 'admin' ali 'editor'")
        return

    with get_db() as db:
        user = db.query(User).filter(User.email == email.lower()).first()
        if not user:
            print(f"Uporabnik {email} ne obstaja v DB. Najprej se prijavi.")
            return
        if new_role:
            user.role = new_role
        if args.media is not None:
            media_list = [m.strip() for m in args.media.split(",") if m.strip()]
            user.allowed_media = _json.dumps(media_list) if media_list else None
        print(f"OK: {email} → role={user.role}, allowed_media={user.allowed_media}")


def cmd_reset(args):
    config = load_config()
    email = args.email or input("Email: ").strip()
    password = args.password or getpass.getpass("Novo geslo: ")

    found = False
    for u in config.get("users", []):
        if u.get("email", "").lower() == email.lower():
            u["password_hash"] = hash_password(password)
            found = True
            break

    if found:
        save_config(config)
        print(f"Geslo ponastavljeno za: {email}")
    else:
        print(f"Uporabnik {email} ni najden.")


def main():
    parser = argparse.ArgumentParser(description="Upravljanje uporabnikov")
    sub = parser.add_subparsers(dest="command")

    add_p = sub.add_parser("add", help="Dodaj uporabnika")
    add_p.add_argument("-e", "--email", default="")
    add_p.add_argument("-n", "--name", default="")
    add_p.add_argument("-p", "--password", default="")

    sub.add_parser("list", help="Izpiši uporabnike")

    rm_p = sub.add_parser("remove", help="Odstrani uporabnika")
    rm_p.add_argument("-e", "--email", default="")

    rst_p = sub.add_parser("reset", help="Ponastavi geslo")
    rst_p.add_argument("-e", "--email", default="")
    rst_p.add_argument("-p", "--password", default="")

    role_p = sub.add_parser("role", help="Nastavi role/allowed_media (DB)")
    role_p.add_argument("-e", "--email", default="")
    role_p.add_argument("--role", choices=["admin", "editor"])
    role_p.add_argument("--media", default=None,
                        help="Comma-separated media ID-ji (samo za editor)")

    args = parser.parse_args()

    if args.command == "add":
        cmd_add(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "remove":
        cmd_remove(args)
    elif args.command == "reset":
        cmd_reset(args)
    elif args.command == "role":
        cmd_role(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
