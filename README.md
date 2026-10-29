# Concours

**Fraud models that keep up with fraudsters.**

Concours serves one niche: payment fraud operations at a fintech, payment company or marketplace that has fraud
analysts but no ML team. The fraud lead uploads transactions, maps five columns, answers three questions
(cases reviewed per day, review cost, how long fraud takes to confirm) and gets, in the same sitting: a
protection report (IDs scrambled, card numbers removed, leaks and future information caught, late labels
handled with an embargo), a working fraud model, and today's review queue sized to the team, with reasons per
case. Analysts mark cases Fraud or Not fraud; those labels feed the next round. When fraud changes, weekly
health and drift checks flag it and an improvement round starts; a new version is promoted only if it passes
five gates. The model keeps improving through a private competition on Apex (Bittensor subnet 1).

Delivery is batch: a daily queue. Real-time scoring is out of scope. The generic engine (churn, leads and the
other templates) stays in the code behind `CONCOURS_ENABLED_TEMPLATES` (default `fraud`). `CONCOURS.md` is
the product overview; `docs/FRAUD_FOCUS_PLAN.md` the change list for this focus.

## Run it

Requirements: Docker Desktop, Python 3.11 with `uv`, Node 22 with `pnpm`. The intake agent and the
agent solver use, in order: `ANTHROPIC_API_KEY` from `backend/.env` if set, else the Claude Code CLI on your
Claude subscription (`claude auth login` once), else cached or default replies.

```bash
./scripts/demo.sh      # reset workspace, fetch the fraud sample, seed the two fraud projects (under 2 minutes when .cache/ is warm)
./scripts/dev.sh       # backend on :8000, frontend on :3000
```

Sign in at http://localhost:3000 with the demo owner the seed creates: `CONCOURS_DEMO_EMAIL` from `.env.example`
and the password the seed generates and writes to `.env` (gitignored; set your own there if you prefer). The dev
servers listen on this machine only (`127.0.0.1`), so nobody on the same Wi-Fi can open the app. `CONCOURS_AUTH=off` in `backend/.env`
turns sign-in off for single-user local use.

Command line: `pipx install ./cli`, then `concours login --url http://127.0.0.1:8000` and `concours --help`
(see `cli/README.md`). Production: `docs/DEPLOY.md` (one VM, Docker Compose, Postgres, HTTPS).

`make dev` and `make demo` are the same commands. On a Mac where `make` fails with the Xcode license
message, run `sudo xcodebuild -license accept` once or `brew install make`.

Tests: `make test`, or `cd backend && .venv/bin/python -m pytest -q` and `cd frontend && pnpm test` (the
copy lint and a type check).

## How it maps onto Apex

Everything about the competition format comes from the public toolkit
`macrocosm-os/apex-competitions-builder` and its worked example. `docs/APEX_CONTRACT.md` records the
verified contract and where it differs from the product brief's assumptions. In short:

- The player is a gym_v1 HTTP server (`/health`, `/reset`, `/act`). Concours keeps solver logic in a plain
  class (`fit`, `predict_proba`) and wraps it once in `backend/player/launch.py`.
- The referee holds the hidden public-check slice and private holdout, drives the player, and writes
  `/data/result.json` with `raw_scores`. Concours's referee is `backend/referee/referee.py`.
- The referee scores fraud as money: each holdout day, the payments with the highest expected loss
  (score x (amount + fee)) up to the team's daily capacity; `raw_scores[0]` is the fraud amount caught per day.
  It reads day and amount from `holdout_meta.csv`, baked into the referee image with the labels.
- A fraud version is promoted only when it passes five gates on the private holdout (hidden data, same rows,
  a day-block bootstrap luck test, no segment regression, speed): `backend/app/fraud/gates.py`. The other
  templates keep the 1% margin in `backend/app/models_registry/promotion.py`.
- "Toolkit validation" means `apex-dev preflight` and `apex-dev screen` pass and Concours's local
  two-container run (same contract as the toolkit's documented loop) produced a valid result. The
  toolkit's own `apex-dev run` is not implemented upstream.
- The handoff zip is a push-ready competition repo: `spec.yaml`, player and referee images, a release
  workflow that builds, signs and pins digests, `HANDOFF.md` in the toolkit's manifest format (with the
  suggested contest reward and the promotion margin), and a prefilled onboarding issue. The private holdout
  is excluded; its checksums are included.

Nothing is launched on a live network. The improvement plan on the Launch screen is illustrative.

## Layout

```
backend/   FastAPI app: fraud (schema, late labels, protection, gates, queue, reasons, drift), intake, packager (checks), models_registry, apex_builder, arena (Docker), serving, handoff; solvers; player; referee
frontend/  Next.js app: Projects home; setup (Your transactions, Three questions, Protect the data); tabs Overview, Review queue, Improve, Data, Launch
data/      fraud sample (scripts/fetch_data.py fraud, scripts/inject_drift.py), other template datasets, defaults
docs/      FRAUD_FOCUS_PLAN.md, APEX_CONTRACT.md, DEMO_SCRIPT.md, CHANGES_PLAN.md, UX_FLOW.md, VALUE_MODEL.md, MODELLING_PLAN.md
vendor/    gym_v1 vendored from the toolkit (do_POST patched)
workspace/ per-project artifacts (gitignored)
```

## Data credits

Fraud: simulated transactions from the Fraud Detection Handbook (ULB Machine Learning Group), see
`data/templates/fraud/SOURCE.md`. Churn: UCI Iranian Churn dataset, CC BY 4.0, see
`data/templates/churn/SOURCE.md`. Leads: UCI Bank Marketing dataset, CC BY 4.0, see
`data/templates/leads/SOURCE.md`.
