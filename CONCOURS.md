# Concours

**A working model today. A global network of solvers keeps improving it.**

Concours turns a spreadsheet prediction problem into a model a business team can use the same day, then keeps
that model improving through a private competition on Apex (a competition network on Bittensor). The customer
buys an outcome: a ranked list each morning that gets better over time. The competition is the engine, never
the product. Customers never see bounties, rewards, tokens, subnets, miners or emissions; Apex is named only on
the Launch screen and in tooltips.

## Principles

- **Day-one value.** Every project produces a usable model (v1) before any contest runs.
- **The contest improves the model.** Improvements are promoted as new versions; nothing is promoted on a
  public score, only on the private holdout.
- **Business outcomes first.** Every result is a sentence about the business ("Fraud caught at 1 false alarm
  per 1,000 good transactions: 30%"), never an algorithm name or a raw metric first. Every number comes from
  code; the language model never writes a number the user sees.
- **Batch delivery.** Lists (fraud review queue, churn call list, lead call list), not real-time APIs.

## Flow

Six steps, in three phases. Lists open from step 4 onward.

| # | Step | Phase | What happens |
|---|---|---|---|
| 1 | Your data | Setup | Upload a CSV (or start from a template). Rows, columns, outcome rate, a 10-row preview, column health. |
| 2 | The goal | Setup | A short chat; the scoring rule fills in live. Target, positive label, how to measure, how to split, what it is worth. |
| 3 | Protect the data | Model | Split (train, public check, private holdout), seven checks (leaks, identifiers, post-outcome names, duplicates, time order, constants, personal data). Then version 1 is built automatically. |
| 4 | Your model | Model | "Your model v1 is ready." Business line, versions timeline, Lists, performance watch, technical details drawer. |
| 5 | Improve | Improve | Improvement attempts arrive; one that beats the active version on the private holdout by the margin is promoted: "New model v2 promoted". Money per month. |
| 6 | Launch | Improve | What will be submitted, the illustrative improvement plan, IP terms, the handoff zip. The only screen that explains Apex. |

## Data model

- **Project**: name, template, stage (`upload`, `intake`, `protect`, `model`, `improve`, `launch`), spec, profile,
  protection report, `active_model_id`, `min_improvement` (default 1% relative), `drift_threshold` (default
  10% relative), `health` (`unknown`, `healthy`, `slipping`), `refresh_daily` (stored preference only).
- **ModelVersion**: `version` (1, 2, ...), `source` (`baseline`, `local_contest`, `apex_contest`),
  `solver_name` (internal, technical drawer only), `private_score`, `public_score`, `metric_name`,
  `business_value` (the headline line), `status` (`active`, `retired`), `created_at`.
- **List**: the rows scored, the version used, `top_n`, the row and action labels from the template, the CSV
  on disk (`rank`, `score`, `action`, then the input columns), `created_at`.
- **Health check**: score on the uploaded labeled rows, the version's holdout score, the relative drop, the
  verdict, a line in plain words.
- **Submission** (an improvement attempt): solver, public and private scores, logs. Unchanged from before.

### Promotion rules (`backend/app/models_registry/promotion.py`)

- After Protect, `baseline_logreg` and `lgbm_default` run through the arena; the better private holdout score
  becomes v1 (source `baseline`).
- A scored attempt is promoted when `candidate_private >= active_private * (1 + min_improvement)` (inverted
  for lower-is-better metrics). The old version is retired. Public scores never promote.
- Each version stores its business line, computed in `shared/translate.py`.

## Endpoints

| Method and path | Purpose |
|---|---|
| `GET /templates` | Template cards, list framing, scripted replies. |
| `POST /projects`, `GET /projects`, `GET /projects/{id}`, `DELETE /projects/{id}` | Projects. `ProjectOut` carries `active_model`, `versions`, `current_result`, `improvement_line`, `result_short`, `health`, `model_status`. |
| `PUT /projects/{id}/settings` | `refresh_daily`, `min_improvement`, `drift_threshold`. |
| `POST /projects/{id}/data`, `GET /projects/{id}/data/profile` | Upload and profile. |
| `POST /projects/{id}/intake`, `GET`, `DELETE` | The goal chat. |
| `PUT /projects/{id}/spec` | Confirm the scoring rule. |
| `POST /projects/{id}/protect`, `GET /projects/{id}/protect/report` | Protection. The POST starts the baseline run that builds v1. |
| `GET /projects/{id}/versions` | Model versions. |
| `POST /projects/{id}/arena/run`, `GET .../leaderboard`, `GET .../stream`, `GET .../status` | Improvement rounds (local solvers), the attempts board, SSE events including `model_version` and `model_promoted`. |
| `POST /projects/{id}/arena/agent` | An agent-written attempt (stretch). |
| `POST /projects/{id}/lists`, `GET /projects/{id}/lists`, `GET .../lists/{lid}`, `GET .../lists/{lid}/download` | Lists. Upload a CSV or pass `sample=true`. |
| `POST /projects/{id}/health` | Performance watch. Upload labeled rows or pass `sample=true` (`degrade=true` for a deliberately worse sample). |
| `GET /projects/{id}/value`, `PUT /projects/{id}/value/params` | Money per month for the active version, compared with v1. |
| `GET /projects/{id}/plan` | The illustrative improvement plan. |
| `POST /projects/{id}/package`, `GET .../package`, `GET .../package/file`, `GET /projects/{id}/handoff` | The Apex package, validation and the handoff zip. HANDOFF.md carries the suggested contest reward and `min_improvement`. |
| `GET /projects/{id}/sample-csv` | Fresh rows for the demo (`labeled`, `degrade`). |

## Copy guidelines

- All strings live in `frontend/lib/copy.ts`. `pnpm test` runs `scripts/copy-lint.mjs`, which fails on
  bounty, reward, TAO, subnet, miner, emission, LightGBM, XGBoost, logistic anywhere in the UI sources, and on
  "Apex" outside the Launch page and the tooltips section.
- Results are sentences about the business. The measure is named in plain words ("Fraud caught at 1 false
  alarm per 1,000 good transactions"), the raw metric is secondary and smaller.
- Models are "v1", "v2". Algorithm names appear only in the technical details drawer (`lib/technical.ts`).
- Attempts on the Improve screen are "Attempt 1", "Attempt 2", labelled "Local solvers (demo)".
- Pricing is an illustrative improvement plan: a subscription plus a success fee on measured improvement over
  v1. No slider, no bounty. The suggested contest reward goes only into HANDOFF.md.
- Complete sentences on cards, no truncation at 1280 px and 1440 px.

## Visual direction

The existing dark theme: near-black canvas, hairline borders, the peach-to-indigo gradient on results, icons
and progress, the cylinder mark and cylinder chart, monospace figures. Results numbers are the hero of every
screen; the gradient is reserved for them, the active version and primary states.

## Repository

See `README.md` for how to run it, `docs/DEMO_SCRIPT.md` for the three-minute demo, `docs/APEX_CONTRACT.md`
for the verified competition contract, `docs/VALUE_MODEL.md` for money per month, `docs/CHANGES_PLAN.md`
for the repositioning change list.
