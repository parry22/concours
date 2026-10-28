"""Accounts: organisations, users, sessions, API keys and invites.

- Passwords: scrypt (n=2**14, r=8, p=1) with a per-user salt.
- Browser sessions: a random token in an HttpOnly cookie; only its SHA-256 is stored.
- API keys (the CLI): `ck_` + random token, shown once; only its SHA-256 is stored.
- Every project belongs to one organisation; a request only sees its organisation's projects.

`CONCOURS_AUTH=off` turns sign-in off for local single-user use: every request acts as the "local" organisation.
`CONCOURS_SIGNUP` decides who may create an account: `first` (only the very first account, the default),
`invite` (with an invite token from an owner) or `open`.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
import time
import uuid
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlmodel import Field as SQLField
from sqlmodel import Session, SQLModel, select

from app.config import env
from app.db import get_session

AUTH_MODE = env("AUTH", "required")  # required | off
SIGNUP = env("SIGNUP", "first")  # first | invite | open
COOKIE = "concours_session"
COOKIE_SECURE = env("COOKIE_SECURE", "0") == "1"
SESSION_DAYS = int(env("SESSION_DAYS", "14"))
LOCAL_ORG = "local"
PUBLIC_PATHS = {"/auth/login", "/auth/signup", "/auth/config", "/healthz", "/readyz", "/docs", "/openapi.json", "/redoc"}

current_org: ContextVar[str | None] = ContextVar("current_org", default=None)
current_user_id: ContextVar[str | None] = ContextVar("current_user_id", default=None)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _id() -> str:
    return uuid.uuid4().hex[:12]


# ---------- tables ----------


class OrgRow(SQLModel, table=True):
    __tablename__ = "org"

    id: str = SQLField(default_factory=_id, primary_key=True)
    name: str
    created_at: datetime = SQLField(default_factory=_now)


class UserRow(SQLModel, table=True):
    __tablename__ = "user_account"

    id: str = SQLField(default_factory=_id, primary_key=True)
    email: str = SQLField(index=True, unique=True)
    name: str = ""
    password_hash: str
    org_id: str = SQLField(index=True)
    role: str = "member"  # owner | member
    created_at: datetime = SQLField(default_factory=_now)
    last_login_at: datetime | None = None


class SessionRow(SQLModel, table=True):
    __tablename__ = "user_session"

    token_hash: str = SQLField(primary_key=True)
    user_id: str = SQLField(index=True)
    expires_at: datetime
    created_at: datetime = SQLField(default_factory=_now)


class ApiKeyRow(SQLModel, table=True):
    __tablename__ = "api_key"

    id: str = SQLField(default_factory=_id, primary_key=True)
    user_id: str = SQLField(index=True)
    org_id: str = SQLField(index=True)
    name: str = ""
    prefix: str = ""  # first characters, to tell keys apart
    token_hash: str = SQLField(index=True, unique=True)
    created_at: datetime = SQLField(default_factory=_now)
    last_used_at: datetime | None = None
    revoked: bool = False


class InviteRow(SQLModel, table=True):
    __tablename__ = "invite"

    token_hash: str = SQLField(primary_key=True)
    org_id: str = SQLField(index=True)
    email: str = ""
    created_by: str = ""
    expires_at: datetime
    used: bool = False


# ---------- secrets ----------


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    key = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt$16384$8$1${salt.hex()}${key.hex()}"


def check_password(password: str, stored: str) -> bool:
    try:
        _, n, r, p, salt, key = stored.split("$")
        got = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p), dklen=len(bytes.fromhex(key)))
        return hmac.compare_digest(got, bytes.fromhex(key))
    except (ValueError, TypeError):
        return False


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_api_key() -> str:
    return "ck_" + secrets.token_urlsafe(32)


# ---------- login throttling (per IP, in memory; a reverse proxy in front adds its own) ----------

_attempts: dict[str, list[float]] = {}
_lock = threading.Lock()
MAX_ATTEMPTS = 10
WINDOW_S = 300


def throttle(ip: str) -> None:
    now = time.monotonic()
    with _lock:
        recent = [t for t in _attempts.get(ip, []) if now - t < WINDOW_S]
        if len(recent) >= MAX_ATTEMPTS:
            raise HTTPException(429, "Too many sign-in attempts. Wait a few minutes and try again.")
        recent.append(now)
        _attempts[ip] = recent


# ---------- resolving the caller ----------


class Caller(BaseModel):
    user_id: str | None
    org_id: str
    email: str | None = None
    role: str = "owner"
    via: str = "session"  # session | api_key | local


def _local(s: Session) -> Caller:
    if s.get(OrgRow, LOCAL_ORG) is None:
        s.add(OrgRow(id=LOCAL_ORG, name="Local"))
        s.commit()
    return Caller(user_id=None, org_id=LOCAL_ORG, via="local")


def resolve(request: Request, s: Session) -> Caller | None:
    if AUTH_MODE == "off":
        return _local(s)
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        key = s.exec(select(ApiKeyRow).where(ApiKeyRow.token_hash == token_hash(auth[7:].strip()), ApiKeyRow.revoked == False)).first()  # noqa: E712
        if key is None:
            return None
        user = s.get(UserRow, key.user_id)
        if user is None:
            return None
        key.last_used_at = _now()
        s.add(key)
        s.commit()
        return Caller(user_id=user.id, org_id=key.org_id, email=user.email, role=user.role, via="api_key")
    token = request.cookies.get(COOKIE)
    if not token:
        return None
    sess = s.get(SessionRow, token_hash(token))
    if sess is None or _aware(sess.expires_at) < _now():
        return None
    user = s.get(UserRow, sess.user_id)
    if user is None:
        return None
    return Caller(user_id=user.id, org_id=user.org_id, email=user.email, role=user.role, via="session")


def _aware(d: datetime) -> datetime:
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


async def require_auth(request: Request, s: Session = Depends(get_session)) -> Caller | None:
    """App-wide dependency: everything except the public paths needs a signed-in caller. Async on purpose: the
    organisation it sets in a context variable is then copied into the thread that runs a sync endpoint."""
    if request.url.path in PUBLIC_PATHS or request.method == "OPTIONS":
        return None
    caller = resolve(request, s)
    if caller is None:
        raise HTTPException(401, "Sign in first.")
    current_org.set(caller.org_id)
    current_user_id.set(caller.user_id)
    request.state.org = caller.org_id  # for the request log, which runs outside this context
    return caller


def caller(request: Request, s: Session = Depends(get_session)) -> Caller:
    c = resolve(request, s)
    if c is None:
        raise HTTPException(401, "Sign in first.")
    return c


# ---------- API ----------

router = APIRouter(prefix="/auth", tags=["auth"])


class SignupIn(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=10, max_length=200)
    name: str = Field("", max_length=120)
    org_name: str = Field("", max_length=120)
    invite: str | None = None


class LoginIn(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    id: str | None
    email: str | None
    name: str = ""
    org_id: str
    org_name: str
    role: str
    auth: str  # required | off


class KeyIn(BaseModel):
    name: str = Field("CLI", max_length=80)


class KeyOut(BaseModel):
    id: str
    name: str
    prefix: str
    created_at: datetime
    last_used_at: datetime | None = None
    token: str | None = None  # only when just created


class InviteIn(BaseModel):
    email: str = ""
    days: int = Field(7, ge=1, le=30)


class InviteOut(BaseModel):
    token: str
    expires_at: datetime


def _user_out(s: Session, c: Caller) -> UserOut:
    org = s.get(OrgRow, c.org_id)
    user = s.get(UserRow, c.user_id) if c.user_id else None
    return UserOut(id=c.user_id, email=c.email, name=user.name if user else "", org_id=c.org_id, org_name=org.name if org else c.org_id,
                   role=c.role, auth=AUTH_MODE)


def _start_session(s: Session, response: Response, user: UserRow) -> None:
    token = secrets.token_urlsafe(32)
    s.add(SessionRow(token_hash=token_hash(token), user_id=user.id, expires_at=_now() + timedelta(days=SESSION_DAYS)))
    user.last_login_at = _now()
    s.add(user)
    s.commit()
    response.set_cookie(COOKIE, token, max_age=SESSION_DAYS * 86400, httponly=True, samesite="lax", secure=COOKIE_SECURE, path="/")


@router.get("/config")
def auth_config(s: Session = Depends(get_session)) -> dict:
    """What the sign-in screen should offer."""
    has_users = s.exec(select(UserRow)).first() is not None
    return {"auth": AUTH_MODE, "signup": SIGNUP, "first_run": not has_users, "can_signup": SIGNUP == "open" or not has_users}


@router.post("/signup", response_model=UserOut)
def signup(body: SignupIn, request: Request, response: Response, s: Session = Depends(get_session)) -> UserOut:
    throttle(request.client.host if request.client else "?")
    email = body.email.strip().lower()
    if "@" not in email:
        raise HTTPException(400, "Enter a valid email address.")
    if s.exec(select(UserRow).where(UserRow.email == email)).first():
        raise HTTPException(409, "An account with this email already exists. Sign in instead.")
    first = s.exec(select(UserRow)).first() is None
    org_id, role = None, "owner"
    if body.invite:
        inv = s.get(InviteRow, token_hash(body.invite))
        if inv is None or inv.used or _aware(inv.expires_at) < _now() or (inv.email and inv.email.lower() != email):
            raise HTTPException(400, "This invite is not valid. Ask for a new one.")
        inv.used = True
        s.add(inv)
        org_id, role = inv.org_id, "member"
    elif not (first or SIGNUP == "open"):
        raise HTTPException(403, "Sign-up needs an invite from your organisation's owner.")
    if org_id is None:
        org = OrgRow(name=body.org_name.strip() or email.split("@")[1])
        s.add(org)
        s.commit()
        org_id = org.id
    user = UserRow(email=email, name=body.name.strip(), password_hash=hash_password(body.password), org_id=org_id, role=role)
    s.add(user)
    s.commit()
    s.refresh(user)
    if first:
        _adopt_orphans(s, org_id)
    _start_session(s, response, user)
    return _user_out(s, Caller(user_id=user.id, org_id=org_id, email=email, role=role))


def _adopt_orphans(s: Session, org_id: str) -> None:
    """The first account takes over projects made before sign-in existed (or with sign-in off)."""
    from app.models import ProjectRow  # noqa: PLC0415

    for p in s.exec(select(ProjectRow).where((ProjectRow.org_id == None) | (ProjectRow.org_id == LOCAL_ORG))).all():  # noqa: E711
        p.org_id = org_id
        s.add(p)
    s.commit()


@router.post("/login", response_model=UserOut)
def login(body: LoginIn, request: Request, response: Response, s: Session = Depends(get_session)) -> UserOut:
    throttle(request.client.host if request.client else "?")
    user = s.exec(select(UserRow).where(UserRow.email == body.email.strip().lower())).first()
    if user is None or not check_password(body.password, user.password_hash):
        raise HTTPException(401, "Email or password is wrong.")
    _start_session(s, response, user)
    return _user_out(s, Caller(user_id=user.id, org_id=user.org_id, email=user.email, role=user.role))


@router.post("/logout")
def logout(request: Request, response: Response, s: Session = Depends(get_session)) -> dict:
    token = request.cookies.get(COOKIE)
    if token:
        sess = s.get(SessionRow, token_hash(token))
        if sess:
            s.delete(sess)
            s.commit()
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@router.get("/me", response_model=UserOut)
def me(c: Caller = Depends(caller), s: Session = Depends(get_session)) -> UserOut:
    return _user_out(s, c)


@router.get("/keys", response_model=list[KeyOut])
def list_keys(c: Caller = Depends(caller), s: Session = Depends(get_session)) -> list[KeyOut]:
    rows = s.exec(select(ApiKeyRow).where(ApiKeyRow.user_id == c.user_id, ApiKeyRow.revoked == False)).all()  # noqa: E712
    return [KeyOut(id=k.id, name=k.name, prefix=k.prefix, created_at=k.created_at, last_used_at=k.last_used_at) for k in rows]


@router.post("/keys", response_model=KeyOut)
def create_key(body: KeyIn, c: Caller = Depends(caller), s: Session = Depends(get_session)) -> KeyOut:
    if c.user_id is None:
        raise HTTPException(400, "API keys need an account; sign-in is off on this server, so the CLI needs no key.")
    token = new_api_key()
    k = ApiKeyRow(user_id=c.user_id, org_id=c.org_id, name=body.name.strip() or "CLI", prefix=token[:10], token_hash=token_hash(token))
    s.add(k)
    s.commit()
    s.refresh(k)
    return KeyOut(id=k.id, name=k.name, prefix=k.prefix, created_at=k.created_at, token=token)


@router.delete("/keys/{key_id}")
def revoke_key(key_id: str, c: Caller = Depends(caller), s: Session = Depends(get_session)) -> dict:
    k = s.get(ApiKeyRow, key_id)
    if k is None or k.user_id != c.user_id:
        raise HTTPException(404, "key not found")
    k.revoked = True
    s.add(k)
    s.commit()
    return {"ok": True}


@router.post("/invites", response_model=InviteOut)
def create_invite(body: InviteIn, c: Caller = Depends(caller), s: Session = Depends(get_session)) -> InviteOut:
    if c.role != "owner":
        raise HTTPException(403, "Only the organisation's owner can invite people.")
    token = secrets.token_urlsafe(24)
    inv = InviteRow(token_hash=token_hash(token), org_id=c.org_id, email=body.email.strip().lower(), created_by=c.user_id or "",
                    expires_at=_now() + timedelta(days=body.days))
    s.add(inv)
    s.commit()
    return InviteOut(token=token, expires_at=inv.expires_at)
