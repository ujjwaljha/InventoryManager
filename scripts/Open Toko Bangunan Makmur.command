#!/bin/bash
# Clear macOS Gatekeeper quarantine so the shop window can open.
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
APP="$DIR/Toko Bangunan Makmur.app"
if [[ ! -d "$APP" ]]; then
  osascript -e 'display alert "Toko Bangunan Makmur" message "Keep this file in the same folder as Toko Bangunan Makmur.app.\n\nSimpan berkas ini di folder yang sama dengan Toko Bangunan Makmur.app."' >/dev/null 2>&1 || true
  exit 1
fi
xattr -cr "$APP" 2>/dev/null || true
codesign --force --deep --sign - --entitlements "$DIR/macos_entitlements.plist" "$APP" 2>/dev/null \
  || codesign --force --deep --sign - "$APP" 2>/dev/null \
  || true
open "$APP"
