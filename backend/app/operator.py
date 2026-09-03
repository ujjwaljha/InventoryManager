from __future__ import annotations

import hashlib
import hmac
import secrets

from fastapi import HTTPException
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.models import ShopSettings
from app.services.checkout import CheckoutError, get_settings

SESSION_KEY = "operator_ok"

_PUBLIC_EXACT = frozenset(
    {
        "/api/health",
        "/api/settings",
        "/api/operator/status",
        "/api/operator/unlock",
    }
)


def normalize_pin(pin: str) -> str:
    digits = "".join(ch for ch in (pin or "") if ch.isdigit())
    if not (4 <= len(digits) <= 8):
        raise CheckoutError("PIN must be 4 to 8 digits")
    return digits


def hash_pin(pin: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt.encode("utf-8"), 120_000).hex()


def pin_is_set(settings: ShopSettings) -> bool:
    return bool((getattr(settings, "operator_pin_hash", None) or "").strip())


def verify_pin(settings: ShopSettings, pin: str) -> bool:
    if not pin_is_set(settings):
        return False
    try:
        candidate = hash_pin(normalize_pin(pin), settings.operator_pin_salt)
    except CheckoutError:
        return False
    return hmac.compare_digest(candidate, settings.operator_pin_hash)


def set_pin(db: Session, pin: str, current_pin: str = "") -> ShopSettings:
    settings = get_settings(db)
    new_pin = normalize_pin(pin)
    if pin_is_set(settings):
        if not verify_pin(settings, current_pin):
            raise CheckoutError("Current PIN is wrong", status_code=401)
    salt = secrets.token_hex(16)
    settings.operator_pin_salt = salt
    settings.operator_pin_hash = hash_pin(new_pin, salt)
    db.flush()
    return settings


def clear_pin(db: Session, current_pin: str) -> ShopSettings:
    settings = get_settings(db)
    if not pin_is_set(settings):
        return settings
    if not verify_pin(settings, current_pin):
        raise CheckoutError("Current PIN is wrong", status_code=401)
    settings.operator_pin_hash = ""
    settings.operator_pin_salt = ""
    db.flush()
    return settings


def _is_public(request: Request) -> bool:
    path = request.url.path.rstrip("/") or "/"
    if path == "/api/shop" or path.startswith("/api/shop/"):
        return True
    if path in _PUBLIC_EXACT:
        return request.method in ("GET", "HEAD", "OPTIONS") or path == "/api/operator/unlock"
    if path == "/api/operator/pin" and request.method == "POST":
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


class OperatorPinMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if not path.startswith("/api/") or _is_public(request):
            return await call_next(request)
        SessionLocal = getattr(request.app.state, "SessionLocal", None)
        if SessionLocal is None:
            return await call_next(request)
        with SessionLocal() as db:
            settings = get_settings(db)
            needed = pin_is_set(settings)
        if not needed:
            return await call_next(request)
        if request.session.get(SESSION_KEY):
            return await call_next(request)
        return JSONResponse({"detail": "Operator PIN required"}, status_code=401)


def require_unlocked(request: Request, db: Session) -> None:
    if not pin_is_set(get_settings(db)):
        return
    if request.session.get(SESSION_KEY):
        return
    raise HTTPException(status_code=401, detail="Operator PIN required")
