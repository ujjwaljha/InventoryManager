from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "TokoBangunanMakmur"
LEGACY_APP_NAME = "WarungPojok"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def bundle_root() -> Path:
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parents[2]


def repo_root() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def frontend_dist() -> Path:
    return bundle_root() / "frontend" / "dist"


def user_data_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share"))
    path = base / APP_NAME
    legacy = base / LEGACY_APP_NAME
    if not path.exists() and legacy.exists():
        return legacy
    path.mkdir(parents=True, exist_ok=True)
    return path


def sqlite_path() -> Path:
    if is_frozen():
        path = user_data_dir() / "inventory.db"
    else:
        path = repo_root() / "data" / "inventory.db"
        path.parent.mkdir(parents=True, exist_ok=True)
    return path


def session_secret() -> str:
    env = os.environ.get("SECRET_KEY")
    if env:
        return env
    if is_frozen():
        path = user_data_dir() / "secret.txt"
        if path.is_file():
            value = path.read_text(encoding="utf-8").strip()
            if value:
                return value
        import secrets

        value = secrets.token_hex(32)
        path.write_text(value, encoding="utf-8")
        return value
    return "corner-shop-dev-secret"
