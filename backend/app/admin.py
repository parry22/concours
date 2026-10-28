"""Operator commands, run on the server (they talk to the database directly):

  python -m app.admin users                          # every account and its organisation
  python -m app.admin reset-password EMAIL           # prompts for a new password, signs out everywhere
  python -m app.admin create-user EMAIL --org ORG_ID [--owner]
  python -m app.admin revoke-keys EMAIL              # revoke every API key of an account

In the compose stack: docker compose -f deploy/docker-compose.yml exec api python -m app.admin users
"""
from __future__ import annotations

import argparse
import getpass
import sys

from sqlmodel import select

from app.auth import ApiKeyRow, OrgRow, SessionRow, UserRow, hash_password
from app.db import init_db, session


def _password() -> str:
    p = getpass.getpass("New password (10+ characters): ")
    if len(p) < 10 or p != getpass.getpass("Again: "):
        raise SystemExit("Passwords must match and be at least 10 characters.")
    return p


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app.admin")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("users")
    p = sub.add_parser("reset-password")
    p.add_argument("email")
    p = sub.add_parser("create-user")
    p.add_argument("email")
    p.add_argument("--org", required=True)
    p.add_argument("--owner", action="store_true")
    p = sub.add_parser("revoke-keys")
    p.add_argument("email")
    a = ap.parse_args(argv)
    init_db()
    with session() as s:
        if a.cmd == "users":
            for u in s.exec(select(UserRow).order_by(UserRow.created_at)).all():
                org = s.get(OrgRow, u.org_id)
                print(f"{u.email:40} {u.role:7} {org.name if org else '?'} ({u.org_id})  last sign-in {u.last_login_at or 'never'}")
            return 0
        user = s.exec(select(UserRow).where(UserRow.email == a.email.strip().lower())).first()
        if a.cmd == "create-user":
            if user:
                raise SystemExit("That email already has an account.")
            if s.get(OrgRow, a.org) is None:
                raise SystemExit(f"No organisation {a.org}. `users` lists them.")
            s.add(UserRow(email=a.email.strip().lower(), password_hash=hash_password(_password()), org_id=a.org, role="owner" if a.owner else "member"))
            s.commit()
            print("Created.")
            return 0
        if user is None:
            raise SystemExit("No account with that email.")
        if a.cmd == "reset-password":
            user.password_hash = hash_password(_password())
            s.add(user)
            for sess in s.exec(select(SessionRow).where(SessionRow.user_id == user.id)).all():
                s.delete(sess)
            s.commit()
            print("Password changed; every browser session of this account is signed out.")
        elif a.cmd == "revoke-keys":
            n = 0
            for k in s.exec(select(ApiKeyRow).where(ApiKeyRow.user_id == user.id, ApiKeyRow.revoked == False)).all():  # noqa: E712
                k.revoked = True
                s.add(k)
                n += 1
            s.commit()
            print(f"Revoked {n} keys.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
