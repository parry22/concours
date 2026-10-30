# Concours

**Fraud models that keep up with fraudsters.**

Concours serves one niche: payment fraud. The user is a fraud operations lead at a fintech, payment company
or marketplace who has fraud analysts but no ML team. They get a working fraud model and a daily review queue
on day one, and a model that keeps adapting as fraudsters change tactics, improved by a global network of
solvers through a private competition on Apex (Bittensor subnet 1). The competition is the engine, never the
product. Customers never see bounties, rewards, tokens, subnets, miners or emissions; Apex is named only on the
Launch screen and in tooltips.

The generic engine (churn, leads, payments, readmissions, attrition, the fairness report, lists, the value
model) stays in the code with its tests, hidden by `config.ENABLED_TEMPLATES` (env `CONCOURS_ENABLED_TEMPLATES`,
default `fraud`). `docs/FRAUD_FOCUS_PLAN.md` lists every change of the fraud focus.

## Principles

- **Day-one value.** Every project produces a working model (v1) and today's review queue before any contest.
- **Money inside capacity.** Every result is fraud money caught per day inside the team's review capacity,
  measured on recent days the model never saw, with labels as they were known then.
- **Promotion is earned.** A new version must pass five gates on the private holdout. Public scores never decide.
- **Batch delivery.** A daily review queue sized to analyst capacity. Real-time scoring is out of scope.
- **Every number comes from code.** No language model writes a number the user sees; the three intake
  questions are parsed in code.

## Flow

Setup, then five tabs.

| Step | What happens |
|---|---|
| Your transactions | Upload a CSV (or the sample). Map columns to `transaction_id`, `transaction_time`, `amount`, `customer_id`, `is_fraud` (required) and `merchant_or_terminal_id`, `currency`, `label_time` (optional), suggested by name. |
| Three questions | Cases reviewed per day (200), cost per review and fee on a missed fraud (10, 0), days until fraud is confirmed (30). Stored as `project.fraud_settings`. |
| Protect the data | IDs hashed with a per-project salt, card numbers dropped, leaks (TX_FRAUD_SCENARIO), future information and clock counters caught, late labels simulated when missing, time split with an embargo. Then v1 builds. |
| Overview | Model card ("$X of fraud caught per day in a 200-case queue", up from v1, net value), versions, weekly health on mature labels, PSI drift, jump forward. |
| Review queue | Today's payments ranked by expected loss, cut at capacity, top three reasons each, Fraud / Not fraud verdicts (new labels), CSV. |
| Improve | Attempts with money per day first, the five gates per attempt, the promotion moment. |
| Data | Protection report, late-label timeline and counts, findings. |
| Launch | What goes to Apex, the illustrative plan, IP terms, handoff. The only screen that explains Apex. |

## Accounts, workers and storage

- Organisations, users (scrypt passwords), session cookies and API keys (`backend/app/auth.py`). Every project
  belongs to one organisation; requests only see their own. The first account is the owner; others join by
  invite. `CONCOURS_AUTH=off` for single-user local use.
- Improvement rounds are jobs in the database, run by `python -m app.worker` (a thread in the API locally).
  Live events are stored rows the stream endpoint reads, so API and worker can be separate processes.
- Uploads, the canonical dataset, the ID map and recent payments are encrypted at rest (`CONCOURS_DATA_KEY`);
  the raw upload is deleted after the columns are confirmed; card-number columns never reach disk.
- Postgres in production, SQLite locally. `docs/DEPLOY.md` covers the VM, backups and monitoring.
- The `concours` command line (`cli/`) drives the same API.

## Late labels (`backend/app/fraud/labels.py`)

From the as-of date E (the simulated today) and D = `label_delay_days`: holdout = 14 days ending D days before
E, leaderboard = 7 days before it, embargo = D days before that (dropped), train = everything earlier, the
newest D days are immature (queue and drift only). Training labels are as known at the training cutoff,
evaluation labels as known at E. Missing `label_time` is simulated: transaction time + U(7, 60) days, seed 42.
Analyst verdicts override labels with `label_time` = the day they were given.

## Metric and gates

- `shared/metrics.fraud_queue`: per day, rank by `score x (amount + fee)`, review the top `daily_capacity`.
  Primary (`fraud_amount_per_day`): mean fraud amount caught per day. Also frauds per day, queue precision,
  false alarms per 1,000 legitimate payments, net value per day (`caught - capacity x review_cost`). The
  referee reads `holdout_meta.csv` (day, amount, new customer).
- `fraud/gates.py`: hidden data, same rows, luck test (day-block bootstrap, 1,000 resamples, 95% wins), no
  segment regression over 5% (amount under 50, 50 to 500, over 500; new and returning customers), speed
  (10,000 rows under 5 s). Stored on the submission and on the version it becomes.
- When the clock moves, the champion is re-scored on the new window first so comparisons stay paired.

## Drift (`backend/app/fraud/service.py`)

Weekly health on mature weeks after the version's holdout: the share of fraud money caught inside capacity,
compared with the same share on the holdout (absolute money cannot fall when a new pattern adds fraud). A
relative drop over 15% or a PSI over 0.2 (amount, hour of day, payments per terminal per day) sets `slipping`;
`POST /projects/{id}/clock` then moves the window and starts a round. `scripts/inject_drift.py` adds card
testing followed by cash-outs at terminals new to the card; `lgbm_velocity` catches it.

## Outside solvers (`backend/app/solve.py`)

Three ways code from outside becomes an attempt, all scored the same way (player container, referee, private
holdout, five gates) and credited on the Improve screen and the version's "what changed" line:

1. **A solver key.** The owner creates a key per solver on Improve ("Outside solvers" card). The solver runs
   `concours solve kit`, writes `submission.py`, runs `concours solve submit`; `concours solve status` shows the
   bar and their attempts. Origin `direct`, version source `outside`. Works today on any Concours server.
2. **Concours's own Bittensor subnet** (`subnet/`): the validator forwards on-chain commitments to
   `POST /projects/{id}/chain/submissions`. Origin `chain`, source `bittensor`. Verified on a local chain.
3. **Apex** (Macrocosmos): the packaged competition. Waiting on activation.

One `submission.py` under 200 KB with `class Solver(SolverBase)` (`fit`, `predict_proba`); `common/base.py`
prepares features. Same code from the same origin is never scored twice. One round at a time per project.

## Endpoints (fraud)

| Method and path | Purpose |
|---|---|
| `POST /projects` | `{template: "fraud", sample}`; `sample_file` and `salt` for the seed. |
| `POST /projects/{id}/data` | Upload transactions (the raw file; mapping next). |
| `GET/PUT /projects/{id}/schema` | The mapping screen and its confirmation (writes the canonical dataset). |
| `POST /projects/{id}/intake`, `GET /intake/fraud-questions` | The three questions. `PUT /projects/{id}/fraud-settings` sets them directly. |
| `POST /projects/{id}/protect` | Fraud protection, then the baseline run that builds v1. |
| `GET /projects/{id}/queue`, `POST .../queue/{tx}/label`, `GET .../queue/download` | Today's review queue, verdicts, CSV. |
| `GET/POST /projects/{id}/drift`, `POST /projects/{id}/clock` | Health and drift; jump forward (`days`, `auto_round`). |
| `POST /projects/{id}/arena/run` | An improvement round (moves the window first if the clock moved). |
| `GET /projects/{id}/versions`, `GET .../arena/leaderboard` | Versions and attempts, each with its gates. |
| `POST /projects/{id}/package`, `GET /projects/{id}/handoff` | The Apex package; HANDOFF.md carries fraud_settings, the embargo and the gate thresholds. |
| `GET/POST /projects/{id}/solvers/keys`, `DELETE .../keys/{key_id}` | Keys for outside solvers (owner side; the token is shown once). |
| `GET /solve/me`, `GET /solve/kit`, `POST /solve/submissions`, `GET /solve/submissions/{id}` | The outside solver's side, authenticated by `X-Solver-Key: sk_...` (no account): the bar, the kit, code in, the attempt's fate out. |
| `GET /projects/{id}/chain`, `PUT .../chain/state`, `POST .../chain/submissions` | The Bittensor validator's intake (`subnet/`). |

## Copy guidelines

- All strings live in `frontend/lib/copy.ts`. `pnpm test` runs `scripts/copy-lint.mjs`, which fails on
  bounty, reward, TAO, subnet, miner, emission, LightGBM, XGBoost, logistic anywhere in the UI sources, and on
  "Apex" outside the Launch page and the tooltips section. It also fails on decision words (reject, deny,
  decline, approve, terminate, fire, disqualify, blacklist and their forms) in the UI sources, and on those words
  plus "flag" in any string of a people template's `defaults.json` (`"people": true`).
- Results are sentences about the business: "$X of fraud caught per day in a 200-case queue", "Up from $Y with
  your first model", "Net value: $Z per day after review costs". Reasons in the queue are plain English
  ("Unusual amount for this customer", "Terminal had recent fraud"), never feature or algorithm names.
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
for the verified competition contract, `docs/FRAUD_FOCUS_PLAN.md` for the fraud focus, `docs/CHANGES_PLAN.md`
for the earlier repositioning.
