#!/usr/bin/env python3
"""Start Toko Bangunan Makmur. Works from source or as a packaged .exe / .app."""

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
        "open_till": "Buka kasir",
        "open_shop": "Buka toko (untuk pembeli)",
        "phones": "HP di Wi‑Fi yang sama — buka alamat ini:",
        "copy": "Salin alamat",
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
    },
    "en": {
        "title": "Toko Bangunan Makmur",
        "starting": "Preparing the shop…",
        "running": "The shop is running. Leave this window open.",
        "failed": "Could not start the shop.",
        "open_till": "Open the till",
        "open_shop": "Open the shop (for customers)",
        "phones": "Phones on the same Wi‑Fi — open this address:",
        "copy": "Copy address",
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
    },
}


def t(key: str) -> str:
    locale = "id"
    if os.environ.get("LANG", "").lower().startswith("en"):
        locale = "en"
    return LANG.get(locale, LANG["id"]).get(key, LANG["en"][key])


def _backend_on_path() -> None:
    if getattr(sys, "frozen", False):
        return
    backend = Path(__file__).resolve().parents[1] / "backend"
    sys.path.insert(0, str(backend))


def die(message: str) -> None:
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


def run_gui(runtime: ShopRuntime) -> None:
    import tkinter as tk
    from tkinter import filedialog, messagebox

    from app.paths import sqlite_path

    url = shop_page()
    till = f"http://127.0.0.1:{PORT}/"
    db = sqlite_path()
    family = "Segoe UI" if sys.platform == "win32" else "Helvetica"

    root = tk.Tk()
    root.title(t("title"))
    root.geometry("560x480")
    root.minsize(480, 420)

    status = tk.StringVar(value=t("running"))
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
        root.clipboard_clear()
        root.clipboard_append(url_var.get())
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
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/backup") as res:
                Path(dest).write_bytes(res.read())
            status.set(t("copied"))
        except OSError:
            if db.is_file():
                shutil.copy2(db, dest)
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
        raw = Path(src).read_bytes()
        if not raw.startswith(b"SQLite format 3"):
            messagebox.showerror(t("title"), t("failed"))
            return
        try:
            import httpx

            res = httpx.post(
                f"http://127.0.0.1:{PORT}/api/backup/restore",
                files={"file": ("inventory.db", raw, "application/octet-stream")},
                timeout=30,
            )
            res.raise_for_status()
            status.set(t("running"))
            webbrowser.open(till)
        except Exception:
            messagebox.showerror(t("title"), t("failed"))

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


def main() -> None:
    freeze_support()
    _backend_on_path()
    from app.paths import is_frozen, sqlite_path, user_data_dir

    os.chdir(user_data_dir() if is_frozen() else Path(__file__).resolve().parents[1])
    sqlite_path()
    ensure_python()
    print(t("starting"), flush=True)
    pip_install()
    ensure_web()

    if health_ok():
        print(t("already"), flush=True)
        webbrowser.open(f"http://127.0.0.1:{PORT}/")
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
        try:
            run_gui(runtime)
        except Exception:
            webbrowser.open(f"http://127.0.0.1:{PORT}/")
            print(t("running"))
            print(shop_page())
            if runtime.thread:
                runtime.thread.join()
    finally:
        runtime.stop()


if __name__ == "__main__":
    main()
