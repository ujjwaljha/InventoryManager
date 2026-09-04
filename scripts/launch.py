#!/usr/bin/env python3
"""Start Toko Bangunan Makmur as a desktop app (Windows .exe / Mac .app, or from source)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from multiprocessing import freeze_support
from pathlib import Path

PORT = 8000

LANG = {
    "id": {
        "title": "Toko Bangunan Makmur",
        "starting": "Menyiapkan toko…",
        "running": "Toko sedang berjalan. Jangan tutup jendela ini.",
        "failed": "Tidak bisa menjalankan toko.",
        "open_till": "Kasir",
        "open_shop": "Lantai toko",
        "phones": "HP di Wi‑Fi yang sama — buka alamat ini:",
        "copy": "Salin alamat HP",
        "copied": "Tersalin",
        "wifi": "Wi‑Fi: biarkan jendela ini terbuka. HP dan komputer lain di Wi‑Fi yang sama melihat stok yang sama.",
        "files": "Bluetooth / AirDrop / USB: simpan salinan, kirim berkasnya, lalu di komputer lain pilih Buka salinan.",
        "save": "Simpan salinan…",
        "load": "Buka salinan…",
        "stop": "Tutup toko",
        "need_python": "Perlu Python 3.12 atau lebih baru.",
        "need_web": "Toko web belum siap. Pasang Node.js dari https://nodejs.org lalu jalankan lagi.",
        "load_confirm": "Ganti data toko ini dengan berkas itu?",
        "no_internet": "Pertama kali perlu internet sebentar untuk memasang pustaka. Coba lagi saat online.",
        "already": "Toko sudah berjalan. Membuka kasir…",
        "menu_shop": "Toko",
        "menu_file": "Berkas",
        "menu_view": "Tampilan",
        "menu_help": "Bantuan",
        "print": "Cetak…",
        "fullscreen": "Layar penuh",
        "about": "Tentang Toko Bangunan Makmur",
        "about_body": "Toko bahan bangunan di jendela sendiri di komputer ini. Staf tetap masuk setelah ditutup. HP di Wi‑Fi yang sama memakai halaman toko.",
        "quit_confirm": "Tutup jendela toko? HP akan kehilangan sambungan langsung.",
        "cancel": "Batal",
        "need_webview": "Tidak bisa membuka jendela aplikasi. Di Windows, pasang Microsoft Edge WebView2.",
    },
    "en": {
        "title": "Toko Bangunan Makmur",
        "starting": "Preparing the shop…",
        "running": "The shop is running. Leave this window open.",
        "failed": "Could not start the shop.",
        "open_till": "Till",
        "open_shop": "Shop floor",
        "phones": "Phones on the same Wi‑Fi — open this address:",
        "copy": "Copy phone address",
        "copied": "Copied",
        "wifi": "Wi‑Fi: leave this window open. Phones and other computers on the same Wi‑Fi see the same stock.",
        "files": "Bluetooth / AirDrop / USB: save a copy, send the file, then on the other computer choose Open a copy.",
        "save": "Save a copy…",
        "load": "Open a copy…",
        "stop": "Stop shop",
        "need_python": "Python 3.12 or newer is required.",
        "need_web": "The shop pages are not built. Install Node.js from https://nodejs.org and try again.",
        "load_confirm": "Replace this shop’s data with that file?",
        "no_internet": "The first start needs the internet briefly to install libraries. Try again when online.",
        "already": "The shop is already running. Opening the till…",
        "menu_shop": "Shop",
        "menu_file": "File",
        "menu_view": "View",
        "menu_help": "Help",
        "print": "Print…",
        "fullscreen": "Full screen",
        "about": "About Toko Bangunan Makmur",
        "about_body": "Building-materials shop in its own window on this computer. Staff stay signed in after you close it. Phones on the same Wi‑Fi still use the shop page.",
        "quit_confirm": "Close the shop window? Phones will lose the live connection.",
        "cancel": "Cancel",
        "need_webview": "Could not open the app window. On Windows, install Microsoft Edge WebView2.",
    },
}


def t(key: str) -> str:
    locale = "id"
    if os.environ.get("LANG", "").lower().startswith("en"):
        locale = "en"
    return LANG.get(locale, LANG["id"]).get(key, LANG["en"][key])


def _attach_stdio() -> None:
    """Windowed .exe/.app have no console; uvicorn calls stdout.isatty()."""
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")


def _backend_on_path() -> None:
    if getattr(sys, "frozen", False):
        return
    backend = Path(__file__).resolve().parents[1] / "backend"
    sys.path.insert(0, str(backend))


def _unblock_windows_dlls() -> None:
    """GitHub zips mark DLLs as blocked; pythonnet cannot load those files."""
    if sys.platform != "win32" or not getattr(sys, "frozen", False):
        return
    roots = [Path(getattr(sys, "_MEIPASS", ".")), Path(sys.executable).resolve().parent]
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if path.suffix.lower() not in {".dll", ".exe", ".pyd"}:
                continue
            try:
                os.remove(f"{path}:Zone.Identifier")
            except OSError:
                pass


def alert(message: str) -> None:
    print(message, file=sys.stderr)
    try:
        import tkinter
        from tkinter import messagebox

        root = tkinter.Tk()
        root.withdraw()
        messagebox.showerror("Toko Bangunan Makmur", message)
        root.destroy()
    except Exception:
        pass


def die(message: str) -> None:
    alert(message)
    sys.exit(1)


def ensure_python() -> None:
    if getattr(sys, "frozen", False):
        return
    if sys.version_info < (3, 12):
        die(t("need_python"))


def pip_install() -> None:
    if getattr(sys, "frozen", False):
        return
    root = Path(__file__).resolve().parents[1]
    cmd = [sys.executable, "-m", "pip", "install", "-q", "-r", str(root / "requirements.txt")]
    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError:
        die(t("no_internet"))


def ensure_web() -> None:
    _backend_on_path()
    from app.paths import frontend_dist, is_frozen, repo_root

    if (frontend_dist() / "index.html").is_file():
        return
    if is_frozen():
        die(t("need_web"))
    npm = shutil.which("npm")
    if not npm:
        die(t("need_web"))
    frontend = repo_root() / "frontend"
    subprocess.check_call([npm, "install"], cwd=frontend)
    subprocess.check_call([npm, "run", "build"], cwd=frontend)
    if not (frontend_dist() / "index.html").is_file():
        die(t("need_web"))


def health_ok() -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/health", timeout=1) as res:
            return res.status == 200
    except OSError:
        return False


def wait_healthy(timeout: float = 40) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if health_ok():
            return True
        time.sleep(0.2)
    return False


class ShopRuntime:
    def __init__(self) -> None:
        self.server = None
        self.thread: threading.Thread | None = None

    def start(self) -> None:
        import uvicorn
        from app.main import create_app

        config = uvicorn.Config(
            create_app(),
            host="0.0.0.0",
            port=PORT,
            log_level="warning",
            access_log=False,
            log_config={
                "version": 1,
                "disable_existing_loggers": False,
                "formatters": {"default": {"format": "%(message)s"}},
                "handlers": {"default": {"class": "logging.NullHandler"}},
                "loggers": {
                    "uvicorn": {"handlers": ["default"], "level": "WARNING"},
                    "uvicorn.error": {"handlers": ["default"], "level": "WARNING"},
                    "uvicorn.access": {"handlers": ["default"], "level": "WARNING"},
                },
            },
        )
        self.server = uvicorn.Server(config)
        self.thread = threading.Thread(target=self.server.run, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        if self.server is not None:
            self.server.should_exit = True


def shop_page() -> str:
    from app.netutil import shop_url as _shop_url

    return _shop_url(PORT)


def till_url() -> str:
    from app.desktop import local_page_url

    return local_page_url("/till", port=PORT)


def floor_url() -> str:
    from app.desktop import local_page_url

    return local_page_url("/shop", port=PORT)


def _dialog_path(result: object) -> Path | None:
    if not result:
        return None
    if isinstance(result, (list, tuple)):
        if not result:
            return None
        result = result[0]
    return Path(str(result))


def _copy_text(text: str) -> None:
    try:
        import tkinter as tk

        root = tk.Tk()
        root.withdraw()
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update()
        root.destroy()
    except Exception:
        pass


def _backup_to(dest: Path) -> bool:
    from app.paths import sqlite_path

    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/backup") as res:
            dest.write_bytes(res.read())
        return True
    except OSError:
        db = sqlite_path()
        if db.is_file():
            shutil.copy2(db, dest)
            return True
    return False


def _restore_from(src: Path) -> bool:
    raw = src.read_bytes()
    if not raw.startswith(b"SQLite format 3"):
        return False
    try:
        import httpx

        res = httpx.post(
            f"http://127.0.0.1:{PORT}/api/backup/restore",
            files={"file": ("inventory.db", raw, "application/octet-stream")},
            timeout=30,
        )
        res.raise_for_status()
        return True
    except Exception:
        return False


def _info(message: str) -> None:
    try:
        import tkinter
        from tkinter import messagebox

        root = tkinter.Tk()
        root.withdraw()
        messagebox.showinfo(t("title"), message)
        root.destroy()
    except Exception:
        print(message, flush=True)


def run_desktop(runtime: ShopRuntime | None) -> None:
    """Native shop window: Edge WebView2 on Windows, WKWebView on Mac."""
    import webview
    from webview.menu import Menu, MenuAction, MenuSeparator

    from app.desktop import (
        MIN_HEIGHT,
        MIN_WIDTH,
        WindowPrefs,
        app_icon_file,
        load_window_prefs,
        save_window_prefs,
        sanitize_local_url,
        webview_start_kwargs,
    )
    from app.paths import bundle_root, user_data_dir

    data_dir = user_data_dir()
    prefs = load_window_prefs(data_dir, port=PORT)
    start_url = sanitize_local_url(prefs.url, port=PORT)
    create_kwargs: dict = {
        "width": prefs.width,
        "height": prefs.height,
        "min_size": (MIN_WIDTH, MIN_HEIGHT),
        "text_select": True,
        "zoomable": True,
        "confirm_close": True,
        "background_color": "#f3eadc",
        "maximized": prefs.maximized,
    }
    if prefs.x is not None and prefs.y is not None:
        create_kwargs["x"] = prefs.x
        create_kwargs["y"] = prefs.y

    window = webview.create_window(t("title"), start_url, **create_kwargs)
    state = WindowPrefs(
        width=prefs.width,
        height=prefs.height,
        x=prefs.x,
        y=prefs.y,
        maximized=prefs.maximized,
        url=start_url,
    )

    def persist() -> None:
        save_window_prefs(data_dir, state)

    def show_till() -> None:
        win = webview.active_window()
        if win:
            win.load_url(till_url())

    def show_shop() -> None:
        win = webview.active_window()
        if win:
            win.load_url(floor_url())

    def save_copy() -> None:
        win = webview.active_window()
        if not win:
            return
        picked = _dialog_path(
            win.create_file_dialog(
                webview.FileDialog.SAVE,
                save_filename="inventory.db",
                file_types=("Shop copy (*.db)", "All files (*.*)"),
            )
        )
        if picked and not _backup_to(picked):
            alert(t("failed"))

    def load_copy() -> None:
        win = webview.active_window()
        if not win:
            return
        picked = _dialog_path(
            win.create_file_dialog(
                webview.FileDialog.OPEN,
                file_types=("Shop copy (*.db)", "All files (*.*)"),
            )
        )
        if not picked:
            return
        try:
            import tkinter as tk
            from tkinter import messagebox

            root = tk.Tk()
            root.withdraw()
            ok = messagebox.askyesno(t("title"), t("load_confirm"))
            root.destroy()
        except Exception:
            ok = True
        if not ok:
            return
        if not _restore_from(picked):
            alert(t("failed"))
            return
        win.load_url(till_url())

    def copy_lan() -> None:
        _copy_text(shop_page())

    def print_page() -> None:
        win = webview.active_window()
        if win:
            win.evaluate_js("window.print()")

    def fullscreen() -> None:
        win = webview.active_window()
        if win:
            win.toggle_fullscreen()

    def show_about() -> None:
        _info(t("about_body"))

    def stop() -> None:
        win = webview.active_window()
        if win:
            win.destroy()

    def on_moved(x: int, y: int) -> None:
        state.x = int(x)
        state.y = int(y)
        persist()

    def on_resized(width: int, height: int) -> None:
        state.width = int(width)
        state.height = int(height)
        persist()

    def on_maximized() -> None:
        state.maximized = True
        persist()

    def on_restored() -> None:
        state.maximized = False
        persist()

    def on_loaded() -> None:
        win = webview.active_window()
        if not win:
            return
        try:
            current = win.get_current_url()
        except Exception:
            current = None
        if current:
            state.url = sanitize_local_url(current, port=PORT)
            persist()

    def on_closed() -> None:
        persist()
        if runtime is not None:
            runtime.stop()

    window.events.moved += on_moved
    window.events.resized += on_resized
    window.events.maximized += on_maximized
    window.events.restored += on_restored
    window.events.loaded += on_loaded
    window.events.closed += on_closed

    file_items = [
        MenuAction(t("save"), save_copy),
        MenuAction(t("load"), load_copy),
        MenuSeparator(),
        MenuAction(t("print"), print_page),
        MenuAction(t("copy"), copy_lan),
    ]
    shop_items = [
        MenuAction(t("open_till"), show_till),
        MenuAction(t("open_shop"), show_shop),
    ]
    if sys.platform == "darwin":
        menu = [
            Menu("__app__", [MenuAction(t("about"), show_about)]),
            Menu(t("menu_file"), file_items),
            Menu(t("menu_shop"), shop_items),
        ]
    else:
        menu = [
            Menu(
                t("menu_file"),
                [*file_items, MenuSeparator(), MenuAction(t("stop"), stop)],
            ),
            Menu(t("menu_view"), [MenuAction(t("fullscreen"), fullscreen)]),
            Menu(t("menu_shop"), shop_items),
            Menu(t("menu_help"), [MenuAction(t("about"), show_about)]),
        ]

    icon = app_icon_file(bundle_root())
    start_kwargs = webview_start_kwargs(
        data_dir,
        gui="edgechromium" if sys.platform == "win32" else None,
        icon=str(icon) if icon else None,
    )
    webview.start(
        menu=menu,
        localization={
            "global.quitConfirmation": t("quit_confirm"),
            "global.quit": t("stop"),
            "global.cancel": t("cancel"),
            "cocoa.menu.about": t("about"),
        },
        **start_kwargs,
    )


def run_gui(runtime: ShopRuntime) -> None:
    """Fallback control panel if the native webview cannot start."""
    import tkinter as tk
    from tkinter import filedialog, messagebox

    url = shop_page()
    till = till_url()
    family = "Segoe UI" if sys.platform == "win32" else "Helvetica"

    root = tk.Tk()
    root.title(t("title"))
    root.geometry("560x480")
    root.minsize(480, 420)

    status = tk.StringVar(value=t("need_webview"))
    url_var = tk.StringVar(value=url)

    pad = {"padx": 16, "pady": 6}
    tk.Label(root, text=t("title"), font=(family, 18, "bold")).pack(anchor="w", **pad)
    tk.Label(root, textvariable=status, wraplength=520, justify="left").pack(anchor="w", padx=16)

    btns = tk.Frame(root)
    btns.pack(fill="x", padx=16, pady=8)
    tk.Button(btns, text=t("open_till"), command=lambda: webbrowser.open(till)).pack(side="left", padx=(0, 8))
    tk.Button(btns, text=t("open_shop"), command=lambda: webbrowser.open(url_var.get())).pack(side="left")

    tk.Label(root, text=t("phones"), wraplength=520, justify="left").pack(anchor="w", padx=16, pady=(12, 0))
    tk.Label(root, textvariable=url_var, font=(family, 12, "bold"), wraplength=520, justify="left").pack(
        anchor="w", padx=16
    )

    def copy_url() -> None:
        _copy_text(url_var.get())
        status.set(t("copied"))

    tk.Button(root, text=t("copy"), command=copy_url).pack(anchor="w", padx=16, pady=4)
    tk.Label(root, text=t("wifi"), wraplength=520, justify="left").pack(anchor="w", padx=16, pady=(10, 0))
    tk.Label(root, text=t("files"), wraplength=520, justify="left").pack(anchor="w", padx=16)

    def save_copy() -> None:
        dest = filedialog.asksaveasfilename(
            title=t("save"),
            defaultextension=".db",
            initialfile="inventory.db",
            filetypes=[("Shop copy", "*.db"), ("All files", "*.*")],
        )
        if not dest:
            return
        if _backup_to(Path(dest)):
            status.set(t("copied"))
        else:
            messagebox.showerror(t("title"), t("failed"))

    def load_copy() -> None:
        src = filedialog.askopenfilename(
            title=t("load"),
            filetypes=[("Shop copy", "*.db"), ("All files", "*.*")],
        )
        if not src:
            return
        if not messagebox.askyesno(t("title"), t("load_confirm")):
            return
        if not _restore_from(Path(src)):
            messagebox.showerror(t("title"), t("failed"))
            return
        status.set(t("running"))
        webbrowser.open(till)

    files = tk.Frame(root)
    files.pack(fill="x", padx=16, pady=10)
    tk.Button(files, text=t("save"), command=save_copy).pack(side="left", padx=(0, 8))
    tk.Button(files, text=t("load"), command=load_copy).pack(side="left")

    def stop() -> None:
        runtime.stop()
        root.destroy()

    tk.Button(root, text=t("stop"), command=stop).pack(anchor="e", padx=16, pady=12)
    root.protocol("WM_DELETE_WINDOW", stop)
    webbrowser.open(till)
    root.mainloop()
    runtime.stop()


def open_shop_ui(runtime: ShopRuntime | None) -> None:
    _unblock_windows_dlls()
    try:
        import webview  # noqa: F401
    except Exception:
        if runtime is None:
            webbrowser.open(till_url())
            return
        run_gui(runtime)
        return
    try:
        run_desktop(runtime)
    except Exception:
        if runtime is None:
            webbrowser.open(till_url())
            return
        run_gui(runtime)


def main() -> None:
    freeze_support()
    _attach_stdio()
    _unblock_windows_dlls()
    _backend_on_path()
    from app.desktop import set_windows_app_id
    from app.paths import is_frozen, sqlite_path, user_data_dir

    set_windows_app_id()

    os.chdir(user_data_dir() if is_frozen() else Path(__file__).resolve().parents[1])
    sqlite_path()
    ensure_python()
    print(t("starting"), flush=True)
    pip_install()
    ensure_web()

    if health_ok():
        print(t("already"), flush=True)
        open_shop_ui(None)
        return

    runtime = ShopRuntime()
    runtime.start()
    try:
        if not wait_healthy():
            runtime.stop()
            die(t("failed"))
        if "--no-gui" in sys.argv:
            print(shop_page(), flush=True)
            if runtime.thread:
                runtime.thread.join()
            return
        open_shop_ui(runtime)
    finally:
        runtime.stop()


if __name__ == "__main__":
    main()
