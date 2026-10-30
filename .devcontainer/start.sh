#!/usr/bin/env bash
# Start the demo stack inside the codespace: API on 127.0.0.1:8000, the production frontend on 0.0.0.0:3000
# (the forwarded port). The frontend proxies /api to the API, so only port 3000 is forwarded.
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.local/bin:$PATH"
mkdir -p workspace
pkill -f "uvicorn app.main:app" 2>/dev/null || true
pkill -f "next-server|next start" 2>/dev/null || true
(cd backend && nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --proxy-headers --forwarded-allow-ips '*' > ../workspace/backend.log 2>&1 < /dev/null &) >/dev/null 2>&1
if [ ! -d frontend/.next ] || [ "${REBUILD:-0}" = 1 ]; then (cd frontend && pnpm build); fi
(cd frontend && nohup pnpm start --port 3000 --hostname 0.0.0.0 > ../workspace/frontend.log 2>&1 < /dev/null &) >/dev/null 2>&1
for _ in $(seq 1 60); do curl -fsS http://127.0.0.1:8000/healthz >/dev/null 2>&1 && break; sleep 1; done
curl -fsS http://127.0.0.1:8000/healthz && echo && echo "[start] backend up; frontend starting on 3000 (log: workspace/frontend.log)"
