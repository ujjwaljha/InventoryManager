"""Helpers for the packaged Mac/Windows shop window."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

APP_ID = "id.tokobangunanmakmur.shop"
APP_DISPLAY_NAME = "Toko Bangunan Makmur"
DEFAULT_PORT = 8000
DEFAULT_WIDTH = 1280
DEFAULT_HEIGHT = 840
MIN_WIDTH = 960
MIN_HEIGHT = 640
MAX_WIDTH = 4000
MAX_HEIGHT = 3000
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


@dataclass
class WindowPrefs:
    width: int = DEFAULT_WIDTH
    height: int = DEFAULT_HEIGHT
    x: int | None = None
    y: int | None = None
    maximized: bool = False
    url: str = ""

    def to_json(self) -> dict[str, Any]:
        return {
            "width": self.width,
            "height": self.height,
            "x": self.x,
            "y": self.y,
            "maximized": self.maximized,
            "url": self.url,
        }


def window_prefs_path(data_dir: Path) -> Path:
    return data_dir / "window.json"


def webview_storage_path(data_dir: Path) -> Path:
    path = data_dir / "webview"
    path.mkdir(parents=True, exist_ok=True)
    return path


def local_page_url(path: str = "/till", *, port: int = DEFAULT_PORT) -> str:
    if not path.startswith("/"):
        path = "/" + path
    parsed = urlparse(f"http://127.0.0.1:{port}{path}")
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["desktop"] = "1"
    return urlunparse(parsed._replace(query=urlencode(query)))


def with_desktop_flag(url: str) -> str:
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["desktop"] = "1"
    return urlunparse(parsed._replace(query=urlencode(query)))


def sanitize_local_url(url: str | None, *, port: int = DEFAULT_PORT, default: str | None = None) -> str:
    fallback = default or local_page_url("/till", port=port)
    if not url:
        return fallback
    parsed = urlparse(url.strip())
    if parsed.scheme != "http":
        return fallback
    host = (parsed.hostname or "").lower()
    if host not in LOCAL_HOSTS:
        return fallback
    if parsed.port not in (None, port):
        return fallback
    if parsed.username or parsed.password:
        return fallback
    path = parsed.path or "/"
    if not path.startswith("/"):
        return fallback
    return with_desktop_flag(urlunparse(("http", f"127.0.0.1:{port}", path, "", parsed.query, "")))


def _as_int(value: Any, default: int, min_v: int, max_v: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(min_v, min(max_v, number))


def clamp_prefs(raw: dict[str, Any] | None, *, port: int = DEFAULT_PORT) -> WindowPrefs:
    data = raw if isinstance(raw, dict) else {}
    prefs = WindowPrefs(
        width=_as_int(data.get("width"), DEFAULT_WIDTH, MIN_WIDTH, MAX_WIDTH),
        height=_as_int(data.get("height"), DEFAULT_HEIGHT, MIN_HEIGHT, MAX_HEIGHT),
        maximized=bool(data.get("maximized")),
        url=sanitize_local_url(str(data.get("url") or ""), port=port),
    )
    if data.get("x") is not None and data.get("y") is not None:
        prefs.x = _as_int(data.get("x"), 40, -200, 8000)
        prefs.y = _as_int(data.get("y"), 40, -200, 8000)
    return prefs


def load_window_prefs(data_dir: Path, *, port: int = DEFAULT_PORT) -> WindowPrefs:
    path = window_prefs_path(data_dir)
    if not path.is_file():
        return clamp_prefs({}, port=port)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return clamp_prefs({}, port=port)
    return clamp_prefs(raw if isinstance(raw, dict) else {}, port=port)


def save_window_prefs(data_dir: Path, prefs: WindowPrefs) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    window_prefs_path(data_dir).write_text(json.dumps(prefs.to_json(), indent=2) + "\n", encoding="utf-8")


def webview_start_kwargs(
    data_dir: Path,
    *,
    gui: str | None = None,
    icon: str | None = None,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "private_mode": False,
        "storage_path": str(webview_storage_path(data_dir)),
    }
    if gui:
        kwargs["gui"] = gui
    if icon:
        kwargs["icon"] = icon
    return kwargs


def set_windows_app_id(app_id: str = APP_ID) -> bool:
    if sys.platform != "win32":
        return False
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
        return True
    except Exception:
        return False


def app_icon_file(root: Path, platform: str | None = None) -> Path | None:
    plat = platform or sys.platform
    if plat == "win32":
        names = ("app-icon.ico", "app-icon.png")
    elif plat == "darwin":
        names = ("app-icon.icns", "app-icon.png")
    else:
        names = ("app-icon.png", "app-icon.ico")
    for name in names:
        path = root / "assets" / name
        if path.is_file():
            return path
    return None
