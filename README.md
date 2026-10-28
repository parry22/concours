# Concours

**A working model today. A global network of solvers keeps improving it.**

Concours turns a spreadsheet prediction problem into a model a business team can use the same day, then
keeps it improving through a private competition on Apex. A company describes the goal in plain English and
uploads a CSV. It gets: a scoring rule a non-ML person can trust, a data protection report (public train
split, private holdout, leakage and PII checks), version 1 of the model within the same sitting, ranked
lists (a fraud review queue, a churn call list, a lead call list), a performance watch, improvement rounds
that promote better versions, and an Apex-ready package with a handoff zip.

Scope: tabular data, one target column, one metric. Templates: card fraud (hero), customer churn and lead
conversion. `CONCOURS.md` is the product overview; `docs/MODELLING_PLAN.md` lists the archetypes planned next.

## Run it

Requirements: Docker Desktop, Python 3.11 with `uv`, Node 22 with `pnpm`. The intake agent and the
agent solver use, in order: `ANTHROPIC_API_KEY` from `backend/.env` if set, else the Claude Code CLI on your
Claude subscription (`claude auth login` once), else cached or default replies.

```bash
./scripts/demo.sh      # reset workspace, fetch data, seed the three demo projects (under 2 minutes when the arena cache is warm)
./scripts/dev.sh       # backend on :8000, frontend on :3000
```

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
- Model versions are promoted on the private holdout score only, by at least `min_improvement` (1% by
  default, the platform's takeover rule). `backend/app/models_registry/promotion.py` holds the rule.
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
backend/   FastAPI app: intake, packager (checks), models_registry (versions, lists, health, plan), apex_builder, arena (Docker), serving, handoff; solvers; player; referee
frontend/  Next.js app: Projects home, then Your data, The goal, Protect the data, Your model (+ Lists), Improve, Launch
data/      template datasets (fetched by scripts/fetch_data.py), intake defaults and list framing
docs/      APEX_CONTRACT.md, DEMO_SCRIPT.md, CHANGES_PLAN.md, UX_FLOW.md, VALUE_MODEL.md, MODELLING_PLAN.md
vendor/    gym_v1 vendored from the toolkit (do_POST patched)
workspace/ per-project artifacts (gitignored)
```

## Data credits

Fraud: simulated transactions from the Fraud Detection Handbook (ULB Machine Learning Group), see
`data/templates/fraud/SOURCE.md`. Churn: UCI Iranian Churn dataset, CC BY 4.0, see
`data/templates/churn/SOURCE.md`. Leads: UCI Bank Marketing dataset, CC BY 4.0, see
`data/templates/leads/SOURCE.md`.
