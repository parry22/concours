#!/usr/bin/env bash
# Start the Brief backend (FastAPI on 8000) and frontend (Next.js on 3000).
# Usage: scripts/dev.sh [backend|frontend|both]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WHAT="${1:-both}"
mkdir -p "$ROOT/workspace"

ensure_backend() {
  if [ ! -x "$ROOT/backend/.venv/bin/uvicorn" ]; then
    echo "[dev] installing backend deps with uv"
    (cd "$ROOT/backend" && uv sync)
  fi
  if [ ! -f "$ROOT/data/templates/fraud/dataset.csv" ] || [ ! -f "$ROOT/data/templates/churn/dataset.csv" ]; then
    echo "[dev] fetching template datasets"
    "$ROOT/backend/.venv/bin/python" -I "$ROOT/scripts/fetch_data.py"
  fi
}

start_backend() {
  ensure_backend
  echo "[dev] backend on http://127.0.0.1:8000 (log: workspace/backend.log)"
  (cd "$ROOT/backend" && exec .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload) 2>&1 | tee "$ROOT/workspace/backend.log"
}

start_frontend() {
  if [ ! -d "$ROOT/frontend/node_modules" ]; then
    echo "[dev] installing frontend deps with pnpm"
    (cd "$ROOT/frontend" && pnpm install)
  fi
  echo "[dev] frontend on http://localhost:3000"
  (cd "$ROOT/frontend" && exec pnpm dev --port 3000)
}

case "$WHAT" in
  backend) start_backend ;;
  frontend) start_frontend ;;
  both)
    start_backend &
    BACK=$!
    start_frontend &
    FRONT=$!
    trap 'kill $BACK $FRONT 2>/dev/null || true' INT TERM EXIT
    wait
    ;;
  *) echo "usage: $0 [backend|frontend|both]"; exit 2 ;;
esac
