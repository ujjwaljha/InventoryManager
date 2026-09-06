#!/usr/bin/env python3
"""Replace a broken/symlink Frameworks/Python with a real Mach-O libpython."""

from __future__ import annotations

import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path


def file_type(path: Path) -> str:
    try:
        return subprocess.check_output(["file", "-b", str(path)], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def is_macho(path: Path) -> bool:
    if not path.is_file():
        return False
    kind = file_type(path)
    return "Mach-O" in kind and "Python script" not in kind


def libpython_candidates() -> list[Path]:
    ver = f"{sys.version_info.major}.{sys.version_info.minor}"
    libdir = Path(sysconfig.get_config_var("LIBDIR") or "")
    ldlib = sysconfig.get_config_var("LDLIBRARY") or f"libpython{ver}.dylib"
    names = [ldlib, f"libpython{ver}.dylib", "Python"]
    roots = [
        libdir,
        Path(sys.base_prefix) / "lib",
        Path(sys.base_prefix) / "lib" / f"python{ver}" / "config-{ver}-darwin",
        Path(sys.base_prefix),
        Path(sys.prefix) / "lib",
    ]
    found: list[Path] = []
    for root in roots:
        for name in names:
            if root and name:
                found.append(root / name)
    return found


def resolve_macho() -> Path:
    for raw in libpython_candidates():
        try:
            path = raw.resolve()
        except OSError:
            continue
        if is_macho(path):
            return path
    raise SystemExit(
        "Could not find a Mach-O libpython on this Mac. "
        + ", ".join(str(p) for p in libpython_candidates()[:6])
    )


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: fix_macos_bundle.py /path/to/App.app")
    app = Path(sys.argv[1])
    target = app / "Contents" / "Frameworks" / "Python"
    fw = target.parent
    if not fw.is_dir():
        raise SystemExit(f"missing Frameworks folder: {fw}")
    print("Frameworks before fix:")
    for child in sorted(fw.iterdir()):
        print(f"  {child.name}: {file_type(child) or ('dir' if child.is_dir() else 'missing')}")
    src = resolve_macho()
    print(f"copying {src} -> {target}")
    fw.mkdir(parents=True, exist_ok=True)
    if target.exists() or target.is_symlink():
        target.unlink()
    shutil.copy2(src, target)
    subprocess.run(["codesign", "--remove-signature", str(target)], check=False)
    kind = file_type(target)
    print(f"Frameworks/Python after fix: {kind}")
    if not is_macho(target):
        raise SystemExit(f"Frameworks/Python is still not Mach-O: {kind}")


if __name__ == "__main__":
    main()
