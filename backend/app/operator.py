from __future__ import annotations

import hashlib
import hmac
import re
import secrets

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.models import User
from app.services.checkout import CheckoutError, get_settings
from app.timeutil import utcnow

SESSION_KEY = "user_id"

DEMO_USERNAME = "admin"
DEMO_PASSWORD = "makmur"

_USERNAME_RE = re.compile(r"^[a-z0-9._-]{2,32}$")

_PUBLIC_GET = frozenset(
    {
        "/api/health",
        "/api/operator/status",
    }
)
_PUBLIC_POST = frozenset(
    {
        "/api/operator/login",
        "/api/operator/setup",
    }
)


def normalize_username(username: str) -> str:
    return (username or "").strip().lower()


def hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000).hex()


def user_count(db: Session) -> int:
    return int(db.scalar(select(func.count()).select_from(User)) or 0)


def active_user_count(db: Session) -> int:
    return int(db.scalar(select(func.count()).select_from(User).where(User.is_active == 1)) or 0)


def get_user_by_username(db: Session, username: str) -> User | None:
    name = normalize_username(username)
    if not name:
        return None
    return db.execute(select(User).where(User.username == name)).scalar_one_or_none()


def user_public(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "is_sales_agent": bool(user.is_sales_agent),
        "is_active": bool(user.is_active),
    }


def current_user(request: Request, db: Session) -> User | None:
    raw = request.session.get(SESSION_KEY)
    if not raw:
        return None
    try:
        user = db.get(User, int(raw))
    except (TypeError, ValueError):
        return None
    if user is None or not user.is_active:
        return None
    return user


def verify_password(user: User, password: str) -> bool:
    if not user or not (password or ""):
        return False
    candidate = hash_password(password, user.password_salt)
    return hmac.compare_digest(candidate, user.password_hash)


def set_password(user: User, password: str) -> None:
    secret = password or ""
    if len(secret) < 4:
        raise CheckoutError("Password must be at least 4 characters")
    if len(secret) > 128:
        raise CheckoutError("Password is too long")
    salt = secrets.token_hex(16)
    user.password_salt = salt
    user.password_hash = hash_password(secret, salt)
    user.updated_at = utcnow()


def create_user(
    db: Session,
    *,
    username: str,
    password: str,
    display_name: str = "",
    is_sales_agent: bool = False,
    is_active: bool = True,
) -> User:
    name = normalize_username(username)
    if not _USERNAME_RE.match(name):
        raise CheckoutError("Username must be 2–32 letters, numbers, dots, underscores, or hyphens")
    if get_user_by_username(db, name):
        raise CheckoutError("Username already exists", status_code=409)
    now = utcnow()
    user = User(
        username=name,
        display_name=(display_name or name).strip() or name,
        password_salt="",
        password_hash="",
        is_sales_agent=1 if is_sales_agent else 0,
        is_active=1 if is_active else 0,
        created_at=now,
        updated_at=now,
    )
    set_password(user, password)
    db.add(user)
    db.flush()
    return user


def list_users(db: Session) -> list[User]:
    return list(db.execute(select(User).order_by(User.display_name, User.username, User.id)).scalars())


def list_sales_agents(db: Session) -> list[User]:
    return list(
        db.execute(
            select(User)
            .where(User.is_sales_agent == 1, User.is_active == 1)
            .order_by(User.display_name, User.username, User.id)
        ).scalars()
    )


def patch_user(
    db: Session,
    user: User,
    *,
    display_name: str | None = None,
    password: str | None = None,
    is_sales_agent: bool | None = None,
    is_active: bool | None = None,
) -> User:
    if display_name is not None:
        user.display_name = display_name.strip() or user.username
    if password:
        set_password(user, password)
    if is_sales_agent is not None:
        user.is_sales_agent = 1 if is_sales_agent else 0
    if is_active is not None:
        next_active = 1 if is_active else 0
        if user.is_active and not next_active and active_user_count(db) <= 1:
            raise CheckoutError("Keep at least one active staff account")
        user.is_active = next_active
    user.updated_at = utcnow()
    db.flush()
    return user


def login_user(request: Request, user: User) -> None:
    request.session[SESSION_KEY] = user.id


def logout_user(request: Request) -> None:
    request.session.pop(SESSION_KEY, None)
    request.session.pop("shopper_id", None)


def seed_demo_users(db: Session) -> None:
    if user_count(db) > 0:
        return
    create_user(
        db,
        username=DEMO_USERNAME,
        password=DEMO_PASSWORD,
        display_name="Admin",
        is_sales_agent=False,
    )
    create_user(db, username="andi", password=DEMO_PASSWORD, display_name="Andi", is_sales_agent=True)
    create_user(db, username="rina", password=DEMO_PASSWORD, display_name="Rina", is_sales_agent=True)


def _is_public(request: Request) -> bool:
    path = request.url.path.rstrip("/") or "/"
    if request.method in ("GET", "HEAD") and path in _PUBLIC_GET:
        return True
    if request.method == "POST" and path in _PUBLIC_POST:
        return True
    if request.method == "OPTIONS":
        return True
    return False


LOCAL_HOSTS = frozenset({"127.0.0.1", "::1", "localhost", "testclient"})


def client_is_local(request: Request) -> bool:
    host = (request.client.host if request.client else "") or ""
    return host in LOCAL_HOSTS


class LanAccessMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if not path.startswith("/api/"):
            return await call_next(request)
        if client_is_local(request):
            return await call_next(request)
        SessionLocal = getattr(request.app.state, "SessionLocal", None)
        if SessionLocal is None:
            return await call_next(request)
        with SessionLocal() as db:
            allowed = bool(int(getattr(get_settings(db), "allow_lan", 0) or 0))
        if allowed:
            return await call_next(request)
        return JSONResponse(
            {"detail": "LAN access is off. Enable it in Settings on this computer."},
            status_code=403,
        )


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if not path.startswith("/api/") or _is_public(request):
            return await call_next(request)
        SessionLocal = getattr(request.app.state, "SessionLocal", None)
        if SessionLocal is None:
            return await call_next(request)
        with SessionLocal() as db:
            user = current_user(request, db)
        if user:
            return await call_next(request)
        return JSONResponse({"detail": "Login required"}, status_code=401)


# Older imports
OperatorPinMiddleware = AuthMiddleware


def require_unlocked(request: Request, db: Session) -> None:
    if current_user(request, db):
        return
    raise HTTPException(status_code=401, detail="Login required")
