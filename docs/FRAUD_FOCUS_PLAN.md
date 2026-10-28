# Fraud focus plan

Source: the "Concours: focus on payment fraud" prompt of 2026-10-28. Concours serves one niche, payment fraud
operations without an ML team. One-liner: "Fraud models that keep up with fraudsters." Everything below is
implemented in this pass unless marked "deviation" or "skipped" with the reason.

## Decisions taken before writing code

- **The generic engine stays.** `config.ENABLED_TEMPLATES = ["fraud"]` (env `CONCOURS_ENABLED_TEMPLATES`,
  comma separated). `GET /templates` and `POST /projects` only accept enabled templates; the other template
  folders, the generic protect path, Lists, the value model and the fairness report stay in the code with their
  tests. The UI never shows a template card.
- **Canonical schema.** On upload the user maps their columns to `transaction_id`, `transaction_time`,
  `amount`, `customer_id`, `is_fraud` (required) and `merchant_or_terminal_id`, `currency`, `label_time`
  (optional). Mapping is auto-suggested by name (`fraud/schema.py`). Confirming writes `dataset.csv` with the
  canonical names; extra columns keep their names and stay as features. The sample keeps the handbook's raw
  names (`TX_DATETIME`, `TX_AMOUNT`, ...) so the mapping screen has something to suggest.
- **A longer sample.** Late labels (7 to 60 days) and a 30-day embargo do not fit the old 31-day file, so the
  sample is 154 days of the same handbook data, 2018-04-01 to 2018-09-01 (`data/templates/fraud/transactions.csv`,
  about 1.5M rows). The old `dataset.csv` stays for the generic tests.
- **The simulated clock ("as of").** Every fraud project has an as-of date: what "today" is. Uploaded data:
  the last transaction. Sample data: day 126 (2018-08-04), so later weeks exist to "jump forward" into for
  the drift demo. Rows after the as-of date are invisible to protect, the queue and health until the clock moves.
- **Windows (time split with embargo).** Working back from the as-of date E with D = `label_delay_days`:
  `holdout` = the 14 days ending at E - D (the newest window whose labels are mature), `leaderboard` = the 7
  days before it, `embargo` = the D days before that (dropped entirely), `train` = everything earlier. The
  newest D days are immature: never scored, only used for today's queue and drift. Training labels are as
  known at the train cutoff (a fraud confirmed after the cutoff is label 0); evaluation labels are as known at
  E (the eval rows all sit before E - D, so they are the mature window). The report says "X frauds were not
  yet confirmed at training time" and how many evaluation frauds were still unconfirmed at E.
- **label_time.** When missing, simulated per fraud: `transaction_time + U(7, 60)` days, seed 42, bounds in
  `fraud_settings.label_delay_min/max`. Analyst labels from the review queue override `is_fraud` with
  `label_time = now` (simulated now = the as-of date).
- **IDs.** `customer_id` and `merchant_or_terminal_id` are replaced by a salted BLAKE2b hash mapped to a
  positive 63-bit integer (solvers still see repeated integer entities for history features). The salt is
  per project (`project.salt`, random; the demo seed fixes it so cached arena runs replay). The mapping is
  written to `workspace/<pid>/private/id_map.csv`, never staged. Solvers no longer use raw entity IDs as
  numeric features, only their history aggregates.
- **Capacity metric.** `shared/metrics.fraud_queue(y, scores, amount, day, capacity, fee, review_cost)`: per
  day, rank by expected loss `score x (amount + fee)`, take the top `capacity`; primary = mean fraud amount
  caught per day; also frauds caught per day, queue precision, false alarms per 1,000 legitimate transactions,
  net value per day (caught minus `capacity x review_cost`), and per-day caught amounts for the gates. The
  referee reads `<split>_meta.csv` (day, amount, new customer flag) baked into the referee image next to the
  labels. The metric name is `fraud_amount_per_day`.
- **Gates replace the 1% margin for fraud.** The generic rule stays for the hidden templates. Each scored
  attempt gets five gate results (`fraud/gates.py`), stored on the submission and on the version it becomes.
  The champion is re-scored on the same holdout when the window moved (it runs first in the round).
- **Health (deviation, wording kept).** Absolute money caught per day cannot fall when fraudsters add a new
  pattern (the old fraud is still caught). Health per simulated week therefore compares the share of fraud
  money caught (money caught / fraud money that day, inside capacity) with the same share on the version's
  holdout. A relative drop over 15% or a PSI over 0.2 on amount, hour of day or per-terminal activity sets
  `slipping`. The alert keeps the prompt's copy: "Your model is catching 31% less fraud."
- **Drift demo.** `scripts/inject_drift.py` (our code) writes `transactions_drift.csv`: from a chosen day,
  card-testing bursts (many transactions under $10 at a compromised set of terminals within minutes, on stolen
  customer cards) followed within 1 to 3 days by cash-out purchases on the tested cards, mid-sized so the
  amount rule does not catch them. A new local solver `lgbm_velocity` keeps per-terminal and per-customer
  recent activity across the scoring stream (past rows only) and catches it.
- **Jump forward.** `POST /projects/{id}/clock {days}` moves the as-of date, runs the weekly health check and,
  if slipping, re-protects on the new window (versions kept) and starts an improvement round with the champion
  plus the local solvers. `auto_round=false` leaves the round to be started by hand (the seeded slipping project).
- **Intake.** For fraud the intake agent is deterministic: three questions with defaults (200 cases a day; 10
  per review and no fee; 30 days to confirm), numbers parsed from the answer, blank means the default. No LLM
  call, so it works offline. Stored as `project.fraud_settings`.
- **Reasons.** Tree models: LightGBM `pred_contrib`. Logistic regression: coefficient x standardized value.
  Feature names map to plain English in `fraud/reasons.py`; names never reach the UI.
- **Frontend.** Setup (Your transactions with the mapping, Three questions, Protecting) then tabs Overview,
  Review queue, Improve, Data, Launch. `/model` and `/lists` redirect to Overview and Review queue.

## Files

### Backend
| File | Change |
|---|---|
| `backend/app/config.py` | `ENABLED_TEMPLATES`, fraud defaults (capacity 200, review cost 10, fee 0, delay 30, delay range 7 to 60, windows 14/7 days, sample as-of day 126), gate thresholds, drift thresholds |
| `backend/app/models.py` | `FraudSettings`, `SchemaMapping`, `MaturitySummary`, `GateResult`, `QueueCase`, `QueueOut`, `WeekHealth`, `DriftOut`; ProjectRow `fraud_settings_json`, `schema_json`, `as_of`, `salt`, `source`, `drift_json`; SubmissionRow and ModelVersionRow `gates_json`; `CaseLabelRow`; primary metric literal `fraud_amount_per_day`; ProtectReport `maturity`, `strategy` "time_embargo" |
| `backend/app/db.py` | New columns and table on existing SQLite files |
| `backend/app/fraud/__init__.py`, `schema.py`, `labels.py`, `protect.py`, `gates.py`, `reasons.py`, `queue.py`, `drift.py`, `intake.py`, `clock.py` | New package: mapping, label maturity and windows, fraud protection, the five gates, reasons, today's queue and analyst labels, PSI and weekly health, the three questions, jump forward |
| `backend/app/packager/checks/future_info.py` | New check: entity-level columns that track the entity's full-period fraud count, and timestamps after the transaction |
| `backend/app/packager/checks/pii.py` | Card numbers (Luhn) are dropped, not masked |
| `backend/app/shared/metrics.py` | `fraud_queue`, `fraud_amount_per_day` in `compute` (meta argument) |
| `backend/app/shared/translate.py` | Fraud lines: "$X of fraud caught per day in a 200-case queue", "Up from $Y with your first model", "Net value: $Z per day after review costs" |
| `backend/referee/referee.py` | Reads `<split>_meta.csv`, passes it to the metric, records seconds per 10,000 rows |
| `backend/app/arena/stage.py` | Stages the meta files for the referee |
| `backend/app/arena/service.py` | Fraud rounds put the champion first when it has no score on the current window, gates after each scored attempt |
| `backend/app/models_registry/promotion.py` | Fraud: promote only when all gates pass; generic rule unchanged |
| `backend/solvers/common/base.py` | Entity IDs are not used as raw numeric features |
| `backend/solvers/lgbm_velocity/submission.py` | New local solver with stream velocity features |
| `backend/app/main.py` | Template flag; endpoints `GET/PUT /projects/{id}/schema`, `PUT /projects/{id}/fraud-settings`, `GET /projects/{id}/queue`, `POST /projects/{id}/queue/{tx}/label`, `GET /projects/{id}/queue/download`, `GET /projects/{id}/drift`, `POST /projects/{id}/clock`, `GET /projects/{id}/maturity` |
| `backend/app/apex_builder/generator.py`, `templates/HANDOFF.md.j2`, `README.md.j2` | fraud_settings, embargo, gate thresholds, the capacity metric |
| `backend/tests/test_fraud_*.py` | Schema mapping (sample and renamed), hashing and Luhn, future info, label maturity, embargo, metrics, every gate (including win-on-average but fail the luck test), reasons, queue labels, PSI and health, drift injection |

### Frontend
| File | Change |
|---|---|
| `frontend/app/page.tsx` | Fraud dashboard: H1, subhead, "Start with your transactions", "Try with sample data", projects table (Name, Today's queue, Model, Updated). No template cards |
| `frontend/app/projects/[id]/upload/page.tsx` | Upload plus the schema-mapping screen |
| `frontend/app/projects/[id]/intake/page.tsx` | The three questions |
| `frontend/app/projects/[id]/protect/page.tsx` | Setup step: protection runs, v1 builds, then Overview |
| `frontend/app/projects/[id]/overview/page.tsx` | New: model card, version timeline, health and drift alerts, jump forward |
| `frontend/app/projects/[id]/queue/page.tsx` | New: today's review queue, reasons, Fraud / Not fraud, CSV |
| `frontend/app/projects/[id]/improve/page.tsx` | Attempts with money per day first, gate results, promotion moment |
| `frontend/app/projects/[id]/data/page.tsx` | New: protection report, label maturity, leakage findings |
| `frontend/app/projects/[id]/model/page.tsx`, `lists/page.tsx` | Redirect to Overview and Review queue |
| `frontend/components/ProjectShell.tsx`, `lib/stages.ts`, `lib/copy.ts`, `lib/api.ts`, `lib/api-types.ts` | Setup steps then tabs, fraud copy, new endpoints |

### Scripts and docs
| File | Change |
|---|---|
| `scripts/fetch_data.py` | `fraud_transactions()`: 154 days |
| `scripts/inject_drift.py` | New |
| `scripts/seed.py`, `scripts/demo.sh` | Two fraud projects: "Card fraud review queue, Q4" (v2, healthy, improving) and "Marketplace payments" (v1, drift, slipping, round ready) |
| `CONCOURS.md`, `README.md`, `docs/DEMO_SCRIPT.md` | Fraud focus |
