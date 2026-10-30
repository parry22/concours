#!/usr/bin/env bash
# Reset and seed the demo: wipe workspace, fetch the fraud sample (and inject the drift pattern), start the
# backend, create the two fraud projects (mapping, three questions, protect, v1, an improvement round, today's
# queue; the second jumps forward into the new fraud pattern and is left slipping).
# Target: under 2 minutes with the arena cache warm; the first ever run builds the player image and runs the
# solvers in Docker (several minutes).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$ROOT/backend/.venv/bin/python"
API="${CONCOURS_API:-${BRIEF_API:-http://127.0.0.1:8000}}"
WS="${CONCOURS_WORKSPACE:-$ROOT/workspace}"   # the backend reads the same variable
PORT="${API##*:}"
KEEP="${KEEP_WORKSPACE:-0}"

if [ "$KEEP" != "1" ]; then
  echo "[demo] wiping $WS/"
  pkill -f "uvicorn app.main:app.*--port $PORT" 2>/dev/null || true
  rm -rf "$WS"/*
fi
mkdir -p "$WS"
[ -x "$PY" ] || (cd "$ROOT/backend" && uv sync)
[ -f "$ROOT/data/templates/fraud/transactions.csv" ] || "$PY" -I "$ROOT/scripts/fetch_data.py" fraud
[ -f "$ROOT/data/templates/fraud/transactions_drift.csv" ] || "$PY" -I "$ROOT/scripts/inject_drift.py"

if ! curl -sf "$API/templates" >/dev/null; then
  echo "[demo] starting backend on $PORT"
  # the subshell closes its own stdout too, or a caller that pipes this script waits until the backend exits
  (cd "$ROOT/backend" && CONCOURS_WORKSPACE="$WS" nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port "$PORT" > "$WS/backend.log" 2>&1 < /dev/null &) >/dev/null 2>&1
  for i in $(seq 1 30); do curl -sf "$API/templates" >/dev/null && break; sleep 1; done
fi

"$PY" "$ROOT/scripts/seed.py" "$API"

# Signed-image runs (scripts/apex_local_run.sh run) are kept under .cache/apex_local/ and re-imported into the
# freshly seeded project, so the Improve screen shows them after every reseed.
if ls "$ROOT"/.cache/apex_local/*/*/out/result.json >/dev/null 2>&1; then
  echo "[demo] importing the signed-image runs"
  CONCOURS_WORKSPACE="$WS" "$ROOT/scripts/apex_local_run.sh" import || echo "[demo] import failed; the seeded projects are still fine"
fi
echo "[demo] done. Open http://localhost:3000 (scripts/dev.sh frontend if not running)."
