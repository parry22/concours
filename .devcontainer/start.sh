#!/usr/bin/env bash
# Start the demo stack inside the codespace: API on 127.0.0.1:8000, the product app on 127.0.0.1:3001 (under /app),
# and the website on 0.0.0.0:3000 (the forwarded port). The website owns / and proxies /app to the app and /api to
# the API, so the link opens on the website, its "Get started" leads to /app/signup, and sign-up lands in the app.
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.local/bin:$PATH"
# Visitors create their own account from the website (each gets an empty workspace of their own).
export CONCOURS_SIGNUP="${CONCOURS_SIGNUP:-open}"
mkdir -p workspace
pkill -f "uvicorn app.main:app" 2>/dev/null || true
pkill -f "next-server|next start" 2>/dev/null || true
(cd backend && nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --proxy-headers --forwarded-allow-ips '*' > ../workspace/backend.log 2>&1 < /dev/null &) >/dev/null 2>&1
if [ ! -d frontend/.next ] || [ "${REBUILD:-0}" = 1 ]; then (cd frontend && pnpm build); fi
[ -d website/node_modules ] || (cd website && pnpm install --frozen-lockfile)
# the website's rewrites are fixed at build time, so the app's address goes in here
export CONCOURS_APP_URL=http://127.0.0.1:3001
if [ ! -d website/.next ] || [ "${REBUILD:-0}" = 1 ]; then (cd website && pnpm build); fi
(cd frontend && nohup pnpm start --port 3001 --hostname 127.0.0.1 > ../workspace/frontend.log 2>&1 < /dev/null &) >/dev/null 2>&1
(cd website && nohup pnpm start --port 3000 --hostname 0.0.0.0 > ../workspace/website.log 2>&1 < /dev/null &) >/dev/null 2>&1
for _ in $(seq 1 60); do curl -fsS http://127.0.0.1:8000/healthz >/dev/null 2>&1 && break; sleep 1; done
curl -fsS http://127.0.0.1:8000/healthz && echo && echo "[start] backend up; website on 3000, app on 3001 under /app (logs: workspace/website.log, workspace/frontend.log)"
