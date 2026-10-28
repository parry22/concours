#!/usr/bin/env bash
# Reset and seed the demo: wipe workspace, fetch data, start the backend, create the three demo projects
# (intake from cached replies, protect, version 1, an improvement round, a list, a health check, one package).
# Target: under 2 minutes with the arena cache warm; the first ever run builds the player image and runs the
# solvers in Docker (several minutes).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$ROOT/backend/.venv/bin/python"
API="${CONCOURS_API:-${BRIEF_API:-http://127.0.0.1:8000}}"
KEEP="${KEEP_WORKSPACE:-0}"

if [ "$KEEP" != "1" ]; then
  echo "[demo] wiping workspace/"
  pkill -f "uvicorn app.main:app" 2>/dev/null || true
  rm -rf "$ROOT/workspace"/*
fi
mkdir -p "$ROOT/workspace"
[ -x "$PY" ] || (cd "$ROOT/backend" && uv sync)
[ -f "$ROOT/data/templates/fraud/dataset.csv" ] && [ -f "$ROOT/data/templates/churn/dataset.csv" ] && [ -f "$ROOT/data/templates/leads/dataset.csv" ] || "$PY" -I "$ROOT/scripts/fetch_data.py"

if ! curl -sf "$API/templates" >/dev/null; then
  echo "[demo] starting backend"
  (cd "$ROOT/backend" && nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 > "$ROOT/workspace/backend.log" 2>&1 < /dev/null &)
  for i in $(seq 1 30); do curl -sf "$API/templates" >/dev/null && break; sleep 1; done
fi

"$PY" "$ROOT/scripts/seed.py" "$API"
echo "[demo] done. Open http://localhost:3000 (scripts/dev.sh frontend if not running)."
