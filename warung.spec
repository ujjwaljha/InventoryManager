# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec: python -m PyInstaller warung.spec"""

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = Path(SPECPATH)
APP_NAME = "Toko Bangunan Makmur"

datas = [(str(ROOT / "frontend" / "dist"), "frontend/dist")]
binaries = []
hiddenimports = collect_submodules("app")

for pkg in (
    "uvicorn",
    "fastapi",
    "starlette",
    "anyio",
    "sqlalchemy",
    "pydantic",
    "pydantic_core",
    "segno",
    "httptools",
    "websockets",
    "httpx",
    "multipart",
    "webview",
    "pythonnet",
    "clr_loader",
    "tzdata",
):
    try:
        extra_d, extra_b, extra_h = collect_all(pkg)
        datas += extra_d
        binaries += extra_b
        hiddenimports += extra_h
    except Exception:
        pass

hiddenimports += [
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "sqlalchemy.dialects.sqlite",
    "python_multipart",
    "tkinter",
    "tkinter.filedialog",
    "tkinter.messagebox",
    "webview",
    "webview.menu",
    "webview.platforms.edgechromium",
    "webview.platforms.winforms",
    "webview.platforms.cocoa",
    "clr",
    "clr_loader",
    "pythonnet",
    "tzdata",
    "zoneinfo",
    "app.main",
    "app.paths",
]

a = Analysis(
    [str(ROOT / "scripts" / "launch.py")],
    pathex=[str(ROOT / "backend")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(ROOT / "scripts" / "pyi_rth_win_unblock.py")],
    excludes=["pytest", "pip", "setuptools"],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=sys.platform not in ("win32", "darwin"),
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=APP_NAME,
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name=f"{APP_NAME}.app",
        icon=None,
        bundle_identifier="id.tokobangunanmakmur.shop",
        info_plist={
            "CFBundleName": APP_NAME,
            "CFBundleDisplayName": APP_NAME,
            "CFBundleShortVersionString": "1.0.0",
            "NSHighResolutionCapable": True,
            "NSLocalNetworkUsageDescription": "Toko Bangunan Makmur shares the shop with phones on the same Wi-Fi.",
        },
    )
