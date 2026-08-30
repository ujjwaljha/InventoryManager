#!/bin/bash
cd "$(dirname "$0")"
if ! command -v python3 >/dev/null 2>&1; then
  open "https://www.python.org/downloads/"
  osascript -e 'display dialog "Install Python 3 from python.org (keep the default options), then double-click this file again.\n\nPasang Python 3 dari python.org, lalu klik dua kali berkas ini lagi." buttons {"OK"}' >/dev/null 2>&1 || true
  exit 1
fi
exec python3 scripts/launch.py
