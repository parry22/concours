# Brief

Brief turns a business prediction problem into a protected, Apex-ready competition, proves it with a
local leaderboard, and hands back a usable model. A company describes the problem in plain English,
uploads a CSV, and gets: a measurable scoring rule a non-ML person can trust, a data protection report
(public train split, private holdout, leakage and PII checks), a competition package in Apex's
`apex.competition.v1` format validated with the Apex toolkit, a local leaderboard, scoring of new
rows with the winner, and a handoff zip.

Scope: tabular data, one target column, one metric. Templates: card fraud (hero) and customer churn.

## Run it

Requirements: Docker Desktop, Python 3.11 with `uv`, Node 22 with `pnpm`. The intake agent and the
agent solver use, in order: `ANTHROPIC_API_KEY` from `backend/.env` if set, else the Claude Code CLI on your
Claude subscription (`claude auth login` once), else cached or default replies.

```bash
./scripts/demo.sh      # reset workspace, fetch data, build images, seed both templates (about 2 minutes when images are cached)
./scripts/dev.sh       # backend on :8000, frontend on :3000
```

`make dev` and `make demo` are the same commands. On a Mac where `make` fails with the Xcode license
message, run `sudo xcodebuild -license accept` once or `brew install make`.

Tests: `cd backend && .venv/bin/python -m pytest -q`.

## How it maps onto Apex

Everything about the competition format comes from the public toolkit
`macrocosm-os/apex-competitions-builder` and its worked example. `docs/APEX_CONTRACT.md` records the
verified contract and where it differs from the product brief's assumptions. In short:

- The player is a gym_v1 HTTP server (`/health`, `/reset`, `/act`). Brief keeps solver logic in a plain
  class (`fit`, `predict_proba`) and wraps it once in `backend/player/launch.py`.
- The referee holds the hidden leaderboard slice and private holdout, drives the player, and writes
  `/data/result.json` with `raw_scores`. Brief's referee is `backend/referee/referee.py`.
- "Validate with Apex toolkit" means `apex-dev preflight` and `apex-dev screen` pass and Brief's local
  two-container run (same contract as the toolkit's documented loop) produced a valid result. The
  toolkit's own `apex-dev run` is not implemented upstream.
- The handoff zip is a push-ready competition repo: `spec.yaml`, player and referee images, a release
  workflow that builds, signs and pins digests, `HANDOFF.md` in the toolkit's manifest format, and a
  prefilled onboarding issue. The private holdout is excluded; its checksums are included.

Nothing is launched on a live network. Pricing on the launch screen is illustrative.

## Layout

```
backend/   FastAPI app: intake, packager (checks), apex_builder, arena (Docker), serving, handoff; solvers; player; referee
frontend/  Next.js app: Projects home, then Your data, Describe the goal, Protect the data, Arena, Use the winner, Launch on Apex
data/      template datasets (fetched by scripts/fetch_data.py) and intake defaults
docs/      APEX_CONTRACT.md, DEMO_SCRIPT.md, UX_FLOW.md (current vs optimised journey)
vendor/    gym_v1 vendored from the toolkit (do_POST patched)
workspace/ per-project artifacts (gitignored)
```

## Data credits

Fraud: simulated transactions from the Fraud Detection Handbook (ULB Machine Learning Group), see
`data/templates/fraud/SOURCE.md`. Churn: UCI Iranian Churn dataset, CC BY 4.0, see
`data/templates/churn/SOURCE.md`.
