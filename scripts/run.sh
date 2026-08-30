#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
python3 -m pip install -q -r requirements.txt
cd "$ROOT/frontend"
npm install
npm run build
cd "$ROOT"
export PYTHONPATH="$ROOT/backend"
exec python3 -m uvicorn app.main:create_app --factory --app-dir backend --host 0.0.0.0 --port 8000
