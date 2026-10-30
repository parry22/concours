#!/usr/bin/env bash
# Run Concours as the validator of its Bittensor testnet subnet (netuid 603) for the project named below.
# Needs: the laptop API on 127.0.0.1:8000 (`./scripts/dev.sh`), the owner wallet in ~/.bittensor/wallets, and
# CONCOURS_VALIDATOR_API_KEY in the repo-root .env. Miners reach the intake on port 8091.
#
#   scripts/testnet_validator.sh            run until Ctrl-C (one pass every 30 s)
#   scripts/testnet_validator.sh --once     one pass, then exit
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; . ./.env; set +a
NETUID="${CONCOURS_NETUID:-603}"
PROJECT="${CONCOURS_VALIDATOR_PROJECT:-$(cd backend && .venv/bin/python -m app.arena.apex_local find "Card fraud on Bittensor testnet")}"
[ -n "$PROJECT" ] || { echo "no project named 'Card fraud on Bittensor testnet'; set CONCOURS_VALIDATOR_PROJECT" >&2; exit 2; }
exec env CONCOURS_API_KEY="$CONCOURS_VALIDATOR_API_KEY" subnet/.venv/bin/concours-validator --network test --netuid "$NETUID" \
  --wallet concours-owner --hotkey validator --project "$PROJECT" --api http://127.0.0.1:8000 --port 8091 --interval 30 "$@"
