import sys

from app.desktop import (
    APP_ID,
    MIN_HEIGHT,
    MIN_WIDTH,
    WindowPrefs,
    app_icon_file,
    clamp_prefs,
    load_window_prefs,
    local_page_url,
    sanitize_local_url,
    save_window_prefs,
    set_windows_app_id,
    webview_start_kwargs,
    webview_storage_path,
)


def test_local_page_url_marks_desktop():
    assert local_page_url("/till") == "http://127.0.0.1:8000/till?desktop=1"
    assert local_page_url("/shop") == "http://127.0.0.1:8000/shop?desktop=1"


def test_sanitize_local_url_keeps_shop_paths():
    assert sanitize_local_url("http://127.0.0.1:8000/shop") == "http://127.0.0.1:8000/shop?desktop=1"
    assert sanitize_local_url("http://localhost:8000/settings") == "http://127.0.0.1:8000/settings?desktop=1"


def test_sanitize_local_url_rejects_strangers():
    fallback = local_page_url("/till")
    assert sanitize_local_url("https://evil.example/till") == fallback
    assert sanitize_local_url("javascript:alert(1)") == fallback
    assert sanitize_local_url("http://127.0.0.1:9999/till") == fallback
    assert sanitize_local_url("http://127.0.0.1:8000@evil.example/") == fallback
    assert sanitize_local_url(None) == fallback


def test_clamp_prefs_and_roundtrip(tmp_path):
    prefs = clamp_prefs({"width": 80, "height": 10, "x": 12, "y": 34, "maximized": 1, "url": "http://127.0.0.1:8000/shop"})
    assert prefs.width == MIN_WIDTH
    assert prefs.height == MIN_HEIGHT
    assert prefs.x == 12
    assert prefs.y == 34
    assert prefs.maximized is True
    assert prefs.url.endswith("/shop?desktop=1")
    save_window_prefs(tmp_path, prefs)
    loaded = load_window_prefs(tmp_path)
    assert loaded == prefs
    broken = tmp_path / "window.json"
    broken.write_text("not-json", encoding="utf-8")
    assert load_window_prefs(tmp_path).width == 1280


def test_webview_keeps_session_cookies(tmp_path):
    kwargs = webview_start_kwargs(tmp_path, gui="edgechromium")
    assert kwargs["private_mode"] is False
    assert kwargs["storage_path"] == str(webview_storage_path(tmp_path))
    assert kwargs["gui"] == "edgechromium"


def test_windows_app_id_is_stable():
    assert APP_ID == "id.tokobangunanmakmur.shop"
    assert set_windows_app_id() is (sys.platform == "win32")


def test_launch_menu_follows_saved_locale(tmp_path, monkeypatch):
    import importlib
    import sys
    from pathlib import Path

    from app.desktop import save_ui_locale

    monkeypatch.setattr("app.paths.user_data_dir", lambda: tmp_path)
    scripts = str(Path(__file__).resolve().parents[2] / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    save_ui_locale("en", tmp_path)
    launch = importlib.import_module("launch")
    importlib.reload(launch)
    assert launch.t("menu_file") == "File"
    assert launch.t("menu_view") == "View"
    assert launch.t("menu_shop") == "Shop"
    assert launch.t("menu_help") == "Help"
    save_ui_locale("id", tmp_path)
    assert launch.t("menu_file") == "Berkas"
    assert launch.t("menu_view") == "Tampilan"


def test_ui_locale_roundtrip_and_env(tmp_path, monkeypatch):
    from app.desktop import load_ui_locale, save_ui_locale, ui_locale_path

    monkeypatch.delenv("IM_LOCALE", raising=False)
    monkeypatch.delenv("LANG", raising=False)
    monkeypatch.delenv("LANGUAGE", raising=False)
    assert save_ui_locale("en", tmp_path) == "en"
    assert ui_locale_path(tmp_path).read_text(encoding="utf-8").strip() == "en"
    assert load_ui_locale(tmp_path) == "en"
    assert save_ui_locale("ID", tmp_path) == "id"
    assert load_ui_locale(tmp_path) == "id"
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setenv("IM_LOCALE", "en")
    assert load_ui_locale(empty) == "en"


def test_app_icon_files_exist():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    png = root / "assets" / "app-icon.png"
    ico = root / "assets" / "app-icon.ico"
    assert png.is_file() and png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    assert ico.is_file() and ico.read_bytes()[:4] == b"\x00\x00\x01\x00"
    found = app_icon_file(root, platform="win32")
    assert found == ico
