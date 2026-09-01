# PyInstaller runtime hook: clear Mark-of-the-Web so pythonnet can load.
# GitHub zip downloads tag Python.Runtime.dll as blocked; .NET then fails
# with "Failed to resolve Python.Runtime.Loader.Initialize".

from __future__ import annotations

import os
import sys
from pathlib import Path


def _unblock(path: Path) -> None:
    ads = f"{path}:Zone.Identifier"
    try:
        os.remove(ads)
    except OSError:
        pass


def _unblock_tree(root: Path) -> None:
    if not root.is_dir():
        return
    for path in root.rglob("*"):
        if path.suffix.lower() in {".dll", ".exe", ".pyd"}:
            _unblock(path)


if sys.platform == "win32" and getattr(sys, "frozen", False):
    _unblock_tree(Path(getattr(sys, "_MEIPASS", ".")))
    _unblock_tree(Path(sys.executable).resolve().parent)
