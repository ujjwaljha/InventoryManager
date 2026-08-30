#!/usr/bin/env python3
"""Start Warung Pojok with a simple window. Safe to double-click."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PORT = 8000
BACKEND = ROOT / "backend"
REQUIREMENTS = ROOT / "requirements.txt"
DIST = ROOT / "frontend" / "dist" / "index.html"

LANG = {
    "id": {
        "title": "Warung Pojok",
        "starting": "Menyiapkan toko… pertama kali bisa sekitar satu menit.",
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
    },
    "en": {
        "title": "Warung Pojok",
        "starting": "Preparing the shop… the first time can take about a minute.",
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
    },
}


def t(key: str) -> str:
    locale = "id"
    try:
        lang = os.environ.get("LANG", "").lower()
        if lang.startswith("en"):
            locale = "en"
    except OSError:
        pass
    return LANG.get(locale, LANG["id"]).get(key, LANG["en"][key])


def die(message: str) -> None:
    print(message, file=sys.stderr)
    try:
        import tkinter
        from tkinter import messagebox

        root = tkinter.Tk()
        root.withdraw()
        messagebox.showerror("Warung Pojok", message)
        root.destroy()
    except Exception:
        pass
    sys.exit(1)


def ensure_python() -> None:
    if sys.version_info < (3, 12):
        die(t("need_python"))


def pip_install() -> None:
    cmd = [sys.executable, "-m", "pip", "install", "-q", "-r", str(REQUIREMENTS)]
    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError:
        die(t("no_internet"))


def ensure_web() -> None:
    if DIST.is_file():
        return
    npm = shutil.which("npm")
    if not npm:
        die(t("need_web"))
    frontend = ROOT / "frontend"
    subprocess.check_call([npm, "install"], cwd=frontend)
    subprocess.check_call([npm, "run", "build"], cwd=frontend)
    if not DIST.is_file():
        die(t("need_web"))


def wait_healthy(timeout: float = 30) -> bool:
    url = f"http://127.0.0.1:{PORT}/api/health"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as res:
                if res.status == 200:
                    return True
        except OSError:
            time.sleep(0.2)
    return False


def start_server() -> subprocess.Popen:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(BACKEND)
    kwargs: dict = {
        "cwd": str(ROOT),
        "env": env,
    }
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:create_app",
            "--factory",
            "--app-dir",
            str(BACKEND),
            "--host",
            "0.0.0.0",
            "--port",
            str(PORT),
        ],
        **kwargs,
    )


def shop_url() -> str:
    sys.path.insert(0, str(BACKEND))
    from app.netutil import shop_url as _shop_url

    return _shop_url(PORT)


def run_gui(proc: subprocess.Popen) -> None:
    import tkinter as tk
    from tkinter import filedialog, messagebox

    url = shop_url()
    till = f"http://127.0.0.1:{PORT}/"
    db = ROOT / "data" / "inventory.db"

    root = tk.Tk()
    root.title(t("title"))
    root.geometry("560x480")
    root.minsize(480, 420)

    status = tk.StringVar(value=t("running"))
    url_var = tk.StringVar(value=url)

    pad = {"padx": 16, "pady": 6}
    tk.Label(root, text=t("title"), font=("Segoe UI", 18, "bold")).pack(anchor="w", **pad)
    tk.Label(root, textvariable=status, wraplength=520, justify="left").pack(anchor="w", padx=16)

    btns = tk.Frame(root)
    btns.pack(fill="x", padx=16, pady=8)
    tk.Button(btns, text=t("open_till"), command=lambda: webbrowser.open(till)).pack(side="left", padx=(0, 8))
    tk.Button(btns, text=t("open_shop"), command=lambda: webbrowser.open(url_var.get())).pack(side="left")

    tk.Label(root, text=t("phones"), wraplength=520, justify="left").pack(anchor="w", padx=16, pady=(12, 0))
    tk.Label(root, textvariable=url_var, font=("Segoe UI", 12, "bold"), wraplength=520, justify="left").pack(
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
        proc.terminate()
        root.destroy()

    tk.Button(root, text=t("stop"), command=stop).pack(anchor="e", padx=16, pady=12)

    def on_close() -> None:
        proc.terminate()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    webbrowser.open(till)
    root.mainloop()
    proc.terminate()


def main() -> None:
    os.chdir(ROOT)
    ensure_python()
    print(t("starting"), flush=True)
    pip_install()
    ensure_web()
    proc = start_server()
    try:
        if not wait_healthy():
            proc.terminate()
            die(t("failed"))
        if "--no-gui" in sys.argv:
            print(shop_url())
            proc.wait()
            return
        try:
            run_gui(proc)
        except Exception:
            webbrowser.open(f"http://127.0.0.1:{PORT}/")
            print(t("running"))
            print(shop_url())
            proc.wait()
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    main()
