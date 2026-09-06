#!/usr/bin/env python3
"""Make the Mac .app able to start: valid libpython + encodings next to it."""

from __future__ import annotations

import encodings
import shutil
import subprocess
import sys
import sysconfig
import zipfile
from pathlib import Path


def file_type(path: Path) -> str:
    try:
        return subprocess.check_output(["file", "-b", str(path)], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def is_macho(path: Path) -> bool:
    if not path.is_file() or path.is_symlink():
        return False
    kind = file_type(path)
    return "Mach-O" in kind and "Python script" not in kind


def strip_sig(path: Path) -> None:
    subprocess.run(["codesign", "--remove-signature", str(path)], check=False)


def libpython_candidates() -> list[Path]:
    ver = f"{sys.version_info.major}.{sys.version_info.minor}"
    libdir = Path(sysconfig.get_config_var("LIBDIR") or "")
    ldlib = sysconfig.get_config_var("LDLIBRARY") or f"libpython{ver}.dylib"
    names = [ldlib, f"libpython{ver}.dylib", "Python"]
    roots = [
        libdir,
        Path(sys.base_prefix) / "lib",
        Path(sys.base_prefix) / "lib" / f"python{ver}" / f"config-{ver}-darwin",
        Path(sys.base_prefix),
        Path(sys.prefix) / "lib",
    ]
    return [root / name for root in roots for name in names if root and name]


def resolve_macho() -> Path:
    for raw in libpython_candidates():
        try:
            path = raw.resolve()
        except OSError:
            continue
        if is_macho(path):
            return path
    raise SystemExit("Could not find a Mach-O libpython on this Mac.")


def zip_has_encodings(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        with zipfile.ZipFile(path) as zf:
            return any(name.replace("\\", "/").startswith("encodings/") for name in zf.namelist())
    except zipfile.BadZipFile:
        return False


def collect_dirs(app: Path) -> list[Path]:
    root = app.resolve().parents[1]
    name = "Toko Bangunan Makmur"
    return [
        root / name / "_internal",
        root / name,
        root / "build" / name,
        Path.cwd() / "dist" / name / "_internal",
        Path.cwd() / "dist" / name,
        Path.cwd() / "build" / name,
    ]


def copy_into(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() or dest.is_symlink():
        if dest.is_dir() and not dest.is_symlink():
            shutil.rmtree(dest)
        else:
            dest.unlink()
    if src.is_dir():
        shutil.copytree(src, dest, symlinks=False)
    else:
        shutil.copy2(src, dest)


def ensure_python_lib(target: Path) -> None:
    if target.is_symlink():
        try:
            resolved = target.resolve()
        except OSError:
            resolved = None
        if resolved and is_macho(resolved):
            print(f"flattening symlink {target} -> {resolved}")
            target.unlink()
            shutil.copy2(resolved, target)
            strip_sig(target)
            return
    if is_macho(target):
        print(f"keeping existing Mach-O {target}")
        strip_sig(target)
        return
    src = resolve_macho()
    print(f"replacing broken {target} with {src}")
    if target.exists() or target.is_symlink():
        target.unlink()
    shutil.copy2(src, target)
    strip_sig(target)
    if not is_macho(target):
        raise SystemExit(f"Frameworks/Python is still not Mach-O: {file_type(target)}")


def ensure_stdlib(fw: Path, app: Path) -> None:
    for folder in collect_dirs(app):
        if not folder.is_dir():
            continue
        for name in ("base_library.zip",):
            src = folder / name
            dest = fw / name
            if src.is_file() and src.resolve() != dest.resolve():
                if not zip_has_encodings(dest) and zip_has_encodings(src):
                    print(f"copying {src} -> {dest}")
                    copy_into(src, dest)
        src_dyn = folder / "python3.12" / "lib-dynload"
        dest_dyn = fw / "python3.12" / "lib-dynload"
        if src_dyn.is_dir() and not dest_dyn.is_dir():
            print(f"copying {src_dyn} -> {dest_dyn}")
            copy_into(src_dyn, dest_dyn)

    dest_zip = fw / "base_library.zip"
    dest_enc = fw / "encodings"
    if zip_has_encodings(dest_zip) or (dest_enc / "__init__.py").is_file():
        print("encodings present")
        return
    src_enc = Path(encodings.__file__).resolve().parent
    print(f"copying encodings package {src_enc} -> {dest_enc}")
    copy_into(src_enc, dest_enc)
    if not (dest_enc / "__init__.py").is_file():
        raise SystemExit("failed to install encodings into the app bundle")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: fix_macos_bundle.py /path/to/App.app")
    app = Path(sys.argv[1])
    fw = app / "Contents" / "Frameworks"
    fw.mkdir(parents=True, exist_ok=True)
    print("Frameworks before fix:")
    for child in sorted(fw.iterdir()) if fw.is_dir() else []:
        extra = file_type(child) if child.is_file() else "dir"
        print(f"  {child.name}: {extra}")
    ensure_python_lib(fw / "Python")
    ensure_stdlib(fw, app)
    print(f"Frameworks/Python: {file_type(fw / 'Python')}")
    print(f"base_library.zip encodings: {zip_has_encodings(fw / 'base_library.zip')}")
    print(f"encodings package: {(fw / 'encodings' / '__init__.py').is_file()}")
    if not is_macho(fw / "Python"):
        raise SystemExit("Frameworks/Python is not Mach-O")
    if not zip_has_encodings(fw / "base_library.zip") and not (fw / "encodings" / "__init__.py").is_file():
        raise SystemExit("encodings is still missing")


if __name__ == "__main__":
    main()
