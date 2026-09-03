#!/usr/bin/env bash
# Build assets/app-icon.icns on macOS (sips + iconutil). No-op elsewhere.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PNG="$ROOT/assets/app-icon.png"
OUT="$ROOT/assets/app-icon.icns"
SET="$ROOT/assets/AppIcon.iconset"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "Skipping .icns (macOS only)."
  exit 0
fi
if [[ ! -f "$PNG" ]]; then
  python3 "$ROOT/scripts/make_app_icon.py"
fi

rm -rf "$SET"
mkdir -p "$SET"
sips -z 16 16 "$PNG" --out "$SET/icon_16x16.png" >/dev/null
sips -z 32 32 "$PNG" --out "$SET/icon_16x16@2x.png" >/dev/null
sips -z 32 32 "$PNG" --out "$SET/icon_32x32.png" >/dev/null
sips -z 64 64 "$PNG" --out "$SET/icon_32x32@2x.png" >/dev/null
sips -z 128 128 "$PNG" --out "$SET/icon_128x128.png" >/dev/null
sips -z 256 256 "$PNG" --out "$SET/icon_128x128@2x.png" >/dev/null
sips -z 256 256 "$PNG" --out "$SET/icon_256x256.png" >/dev/null
sips -z 512 512 "$PNG" --out "$SET/icon_256x256@2x.png" >/dev/null
sips -z 512 512 "$PNG" --out "$SET/icon_512x512.png" >/dev/null
sips -z 1024 1024 "$PNG" --out "$SET/icon_512x512@2x.png" >/dev/null
iconutil -c icns "$SET" -o "$OUT"
rm -rf "$SET"
echo "$OUT"
