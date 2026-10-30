#!/usr/bin/env bash
# Codespace setup: Python 3.11 venv through uv, frontend dependencies, a production build of the frontend.
# Sample data and the warm caches are copied in afterwards with `gh codespace cp` (they are not in git).
set -euo pipefail
cd "$(dirname "$0")/.."
pip install --quiet --user uv
export PATH="$HOME/.local/bin:$PATH"
(cd backend && uv python install 3.11 && uv sync)
corepack enable && corepack prepare pnpm@10.0.0 --activate
(cd frontend && pnpm install --frozen-lockfile)
(cd website && pnpm install --frozen-lockfile)
echo "[setup] done; copy data/ and .cache/ in, then run .devcontainer/start.sh"
