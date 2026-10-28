# Modelling plan: problem archetypes beyond fraud and churn

Concours ships two templates, card fraud and customer churn. Both are row-scored binary problems with one
target column, and the engine behind them (split, protect, referee, value model, solvers) was built for
that shape. This document lists the next problem archetypes the platform should model, what each one
needs from the engine, and the order to build them in. Value-model arithmetic is being reworked
separately (`docs/VALUE_MODEL.md`); here each archetype only says which value parameters it maps onto.

## 1. What the engine supports today

| Capability | State |
|---|---|
| Task types | `binary` fully. `regression` is stubbed: `wape` / `mae` exist in `shared/metrics.py` and `metric_policy.py` picks them, but no solver, no value model, no template |
| Metrics | `recall_at_fpr`, `recall_at_top_k`, `pr_auc`, `roc_auc`, `wape`, `mae` |
| Metric policy | positive rate under 5% -> fraud shape; 5% or more -> churn shape; numeric target with many values -> regression |
| Split | time-ordered 70/10/20 when a time column exists, else stratified on the target |
| Features | shared `FeaturePrep`: time parts, categorical codes, optional per-entity history (counts, positives, 28-day window, amount ratio) |
| Solvers | logistic regression baseline, LightGBM default, LightGBM tuned, agent-written solver |
| Player contract | `/act` takes `{columns, rows}` and returns `{scores: [float]}`, one float per row |
| Value model | confusion matrix at an operating point, priced with `rows_per_month`, `positive_rate`, `value_per_positive`, `action_success_rate`, `cost_per_action`, `cost_per_false_positive` |
| Protection | PII, id-like, constant, post-outcome name, target leak, temporal, cross-split duplicates |

Everything binary and row-scored fits with no engine change. Everything else needs one of four
extensions, listed in section 3.

## 2. Archetypes

Grouped by how much engine work they need. Each row gives the business framing, the data shape, the
metric the policy should pick, the split, the value mapping, the solver family, a public dataset with a
usable license, and the demo line.

### Tier A: binary, row-scored. Engine unchanged, new template folder only

**A1. Lead conversion / propensity to buy** (built 2026-10-28 as template `leads`)
- Problem: which prospects to call or email first with a fixed sales capacity.
- Target: converted (yes/no). Positive rate 5 to 15%.
- Metric: `recall_at_top_k`, `top_k` = contact capacity share (default 0.10). Secondary `roc_auc`.
- Split: stratified. The public file has no year, and its last months are a different campaign regime (about
  a third of contacts convert against 6% at the start), so a time split trains on one campaign and tests on
  another and no solver beats the baseline. Measured 2026-10-28: time split 24% / 29% on the leaderboard
  slice for baseline / tuned but 16% / 16% on the holdout; stratified 34% / 44%.
- Value: `value_per_positive` = margin per conversion, `action_success_rate` = share of contacted
  converters attributable to the contact, `cost_per_action` = call cost, `cost_per_false_positive` = 0.
- Solvers: current three plus the agent solver, unchanged.
- Dataset: UCI Bank Marketing (dataset 222), 45,211 rows, 11.7% positive, CC BY 4.0. Leak to plant
  or detect: `duration` (call length, known only after the call). This is a textbook post-outcome
  column and the protect step should drop it the way it drops `TX_FRAUD_SCENARIO`.
- Demo line: "Of people who would buy, reached by calling your top 10%: 41% to 63%."

**A2. Loan default / credit risk**
- Problem: which applications to decline or send to manual review.
- Target: defaulted within N months. Positive rate 5 to 25%.
- Metric: `recall_at_top_k` where k is the decline-or-review share (default 0.10). Secondary `roc_auc`
  (lenders quote Gini = 2 x AUC - 1; show both words).
- Split: time by application date when present (concept drift is real here), else stratified.
- Value: `value_per_positive` = loss given default x exposure, `action_success_rate` = 1.0 (a declined
  loan cannot default), `cost_per_action` = review cost, `cost_per_false_positive` = lost margin on a good
  customer declined.
- Solvers: unchanged. Monotone constraints on income and debt ratio are a credible "tuned" variant.
- Dataset: UCI Default of Credit Card Clients (dataset 350), 30,000 rows, 22.1% positive, CC BY 4.0.
- Extra protection: a protected-attribute check (sex, age, marital status, zip) that warns and offers to
  drop. Needed for credibility in lending; see 3.4.
- Demo line: "Of loans that go bad, caught in the riskiest 10% of applications: 32% to 51%."

**A3. Insurance claim fraud**
- Same shape as card fraud (rare positive, `recall_at_fpr`), different vocabulary and entities
  (policy, claimant, repair shop). Mostly proves the fraud path is not card-specific.
- Dataset: no clean open-licensed option found yet. Kaggle "Vehicle Insurance Claim Fraud" has unclear
  terms. Hold until a dataset is confirmed, or synthesise.

**A4. Hospital readmission within 30 days**
- Problem: which discharged patients get a follow-up call or home visit.
- Target: readmitted under 30 days. Positive rate about 11%.
- Metric: `recall_at_top_k` (outreach capacity). Secondary `roc_auc`.
- Split: stratified (no admission date in the public data).
- Value: `value_per_positive` = readmission cost or penalty, `action_success_rate` = share of readmissions
  an outreach prevents (default 0.2), `cost_per_action` = visit cost.
- Dataset: UCI Diabetes 130-US hospitals (dataset 296), 101,766 rows, CC BY 4.0. Target column
  `readmitted` has three values (`<30`, `>30`, `NO`): positive label `<30`, the rest negative. Intake
  must support a positive label that is a string, which `ProblemSpec.positive_label` already allows.
- Extra protection: PII is already masked; add the protected-attribute warning from A2.

**A5. Equipment failure (predictive maintenance)**
- Problem: which machines or parts to inspect this week.
- Target: failure in the next window. Positive rate 1 to 5%.
- Metric: `recall_at_fpr` when inspections are expensive and rare, else `recall_at_top_k`.
- Split: time by sensor timestamp; entity history by machine id. This is the archetype that shows off
  `FeaturePrep.history` (previous failures per machine, 28-day window) outside fraud.
- Value: `value_per_positive` = unplanned downtime cost, `cost_per_action` = inspection cost,
  `action_success_rate` = share of failures an inspection prevents.
- Dataset: UCI AI4I 2020 (dataset 601), 10,000 rows, 3.4% failures, CC BY 4.0. No timestamp, so the
  first version splits stratified. Leak to detect: the five failure-mode flags (`TWF`, `HDF`, `PWF`,
  `OSF`, `RNF`) are post-outcome columns, same pattern as `TX_FRAUD_SCENARIO`.

**A6. Employee attrition** (HR). Same shape as churn, small public data (IBM HR, 1,470 rows, license
unclear). Low priority; listed so sales conversations have an answer.

### Tier B: regression. Finishes the stubbed path

**B1. Demand forecasting (units per item per period)**
- Problem: how much to stock or staff next week.
- Target: numeric count. Metric `wape` (already in the referee), secondary `mae`. Scale-free, so one
  number works across items.
- Split: time only, and forward-chained with a gap equal to the horizon so no leaderboard row sits inside
  the window a train row could see. Current `split_by_time` has no gap; see 3.2.
- Value: needs a different formula from the confusion matrix: over-forecast costs holding or waste per
  unit, under-forecast costs a lost sale per unit. Map onto the parameter list as `value_per_positive`
  (margin per unit sold) and `cost_per_false_positive` (holding or waste per unit over), with
  `action_success_rate` unused. The arithmetic belongs to the value-model work.
- Solvers: `LGBMRegressor` with `objective="tweedie"` (counts with many zeros) or `"l1"` (aligns with
  WAPE); baseline is last-period value or per-item mean. `FeaturePrep` needs lags and rolling means by
  entity, which the history block can grow into (it already groups by entity and time).
- Player: unchanged, `scores` is the prediction.
- Dataset: UCI Bike Sharing (dataset 275), 17,379 hourly rows, target `cnt`, CC BY 4.0. Leaks:
  `casual` and `registered` sum to the target and must be dropped (target-leak check should catch
  them: perfect correlation with the target).
- Demo line: "Weekly forecast error as a share of demand: 31% to 18%."

**B2. Claim severity / customer lifetime value (amount regression)**
- Heavy-tailed money target. Metric `wape`; solver `LGBMRegressor(objective="gamma")` or log-target.
- Dataset: French motor claims (`freMTPL2`, OpenML, public domain-style license, 678k policies) is the
  standard; confirm the license before fetching.

**B3. Delivery time / ETA**
- Metric `mae` in minutes; value from late-delivery penalties. No open dataset confirmed; hold.

### Tier C: new engine capability

**C1. Uplift (who changes behaviour because we acted)**
- Why it matters: the churn template's `action_success_rate` is a guess today. Uplift models measure it.
  This is the archetype that turns "who will leave" into "who will stay if we call", which is what a
  retention budget actually buys.
- Data: a treatment column (contacted or not) plus the outcome. Requires a past campaign with a
  control group.
- Metric: Qini coefficient or area under the uplift curve at the contact share. New metric in
  `shared/metrics.py`; the referee passes the treatment column to it, so `CONFIG_JSON` carries
  `treatment_column`.
- Solvers: T-learner (two LightGBMs, score = p(outcome | treated) - p(outcome | control)) as the
  baseline, X-learner as the tuned variant. Both fit the `fit` / `predict_proba` shape if `fit` receives the
  treatment flag as a column and `predict_proba` returns the uplift score.
- Value: `action_success_rate` becomes measured per row instead of a default. The value model can keep
  its formula with TP replaced by incremental positives.
- Dataset: Hillstrom MineThatData e-mail (64,000 rows, free for research use; confirm redistribution).
  Criteo Uplift (13.9M rows) is CC BY-NC-SA, so not for a commercial demo.

**C2. Multiclass routing (ticket category, product category, next best action)**
- Metric: macro-F1 or top-1 accuracy; secondary log loss.
- Engine change: `scores` becomes a list of lists (one probability per class), the referee reads
  `classes` from config, the value model prices a routing error by class pair. Medium effort, broad
  demand.

**C3. Ranking within a group (which offer per customer, which listing per query)**
- Metric: NDCG@k per group, averaged. Needs a `group_column` in the spec and a grouped split
  (all rows of a group stay in one part). LightGBM `lambdarank` is the solver.

**C4. Time-to-event (when will they leave)**
- Metric: concordance index. Target is a duration plus an event flag, so two target columns.
  Survival boosting needs a library outside the current allowlist. Lowest priority; most of the
  business value is captured by C1 plus churn.

**C5. Unlabelled anomaly detection.** Out of scope: the referee needs labels to score.

## 3. Engine extensions the tiers need

### 3.1 Archetype as data, not code
`metric_policy.py` hard-codes vocabulary (`_WORDS`), rate hints and the two business shapes; the frontend
hard-codes `TEMPLATE_METRIC` and template icons. Move all of it into `data/templates/<id>/defaults.json`:

```json
{
  "name": "Lead conversion",
  "description": "Call the prospects most likely to buy first.",
  "dataset": "dataset.csv",
  "target_column": "y",
  "positive_label": "yes",
  "time_column": null,
  "id_columns_hint": [],
  "primary_metric": "recall_at_top_k",
  "metric_params": {"top_k": 0.10},
  "secondary_metric": "roc_auc",
  "business_template": "propensity",
  "words": {"positive": "buyers", "negative": "prospects", "short": "buyers"},
  "rate_hint": 0.12,
  "economics_defaults": {"value_per_positive": 180.0, "action_success_rate": 0.3, "cost_per_action": 3.0, "cost_per_false_positive": 0.0},
  "metric_line": "Buyers reached in the riskiest 10%",
  "intake_goal": "We want to know which prospects to call first.",
  "scoring_sample": "scoring_sample.csv",
  "known_leaks": ["duration"]
}
```

`Template` in `models.py` becomes a plain string validated against the folder list. `metric_policy`
keeps deciding the metric from the data; the template only supplies words and defaults.

### 3.2 Split strategies
Add `grouped` (all rows of an entity in one part, for C3 and for any customer-level target with many rows
per customer) and `time_gap` (time split with a horizon gap, for B1). `ProtectReport.strategy` grows
accordingly.

### 3.3 Metrics and score shapes
Add `precision_at_top_k`, `qini`, `macro_f1`, `ndcg_at_k`, `concordance`. The referee's `compute()`
dispatch already takes the metric name from config, so binary and regression additions are one function
each. Multiclass and ranking change the `scores` payload, so they land together with a player contract
version bump (`gym_v1` observation stays, Concours's `{scores}` body gains an optional `classes` list).

### 3.4 Protection checks
- Protected attributes (sex, gender, age, race, ethnicity, religion, nationality, marital status,
  postcode): warn, explain, offer to drop. Required for A2 and A4.
- Target-sum leak: columns whose sum or difference equals the target (B1 `casual` + `registered`).
  The current target-leak check looks at single-column correlation; add a two-column pass over numeric
  columns.
- Post-outcome names: extend the word list with maintenance and health vocabulary (`failure_type`,
  `discharge_disposition`, `duration` of a call).

### 3.5 Value model
Each archetype above maps onto the six existing parameter keys except B1, which needs an
over/under cost pair. Keep the parameter list as the contract and let the arithmetic work decide
whether the regression case is a second formula or the same one with renamed cells.

### 3.6 Solvers
One folder per family, picked by `task_type`:

| Task | Baseline | Default | Tuned |
|---|---|---|---|
| binary | logistic regression | LightGBM | LightGBM + history + class weight |
| regression | per-entity mean, last value | LightGBM (`l1`) | LightGBM (`tweedie`) + lags |
| uplift | T-learner, two logistic | T-learner, two LightGBM | X-learner |
| multiclass | logistic (multinomial) | LightGBM multiclass | LightGBM + class weights |

The agent solver prompt gains the task type and the metric so a model writes the right estimator.

## 4. Build order

| Order | Archetype | Engine work | Why first |
|---|---|---|---|
| 1 | A1 Lead conversion | none beyond 3.1 | Done. Open license, planted leak (`duration`) caught through the template's `known_leaks` list, proves the churn path is generic. |
| 2 | A2 Loan default | 3.4 protected attributes | Lending is the buyer persona next to fraud; fairness check is a selling point. |
| 3 | A5 Predictive maintenance | none | Shows entity history outside fraud; manufacturing audience. |
| 4 | B1 Demand forecasting | 3.2 time gap, regression solvers, value formula | Completes the regression path already half-built. |
| 5 | C1 Uplift | new metric, treatment column, two-model solvers | Turns `action_success_rate` from a default into a measurement. Differentiator. |
| 6 | A4 Readmission | string positive label, 3.4 | Healthcare audience; data is large and open. |
| 7 | C2 Multiclass, C3 Ranking | score shape change | After the above; both need the contract bump. |

Step 1 landed the 3.1 refactor: words, rate hint, metric line, scripted replies and known leaks live in
`defaults.json`, `/templates` serves the card fields, and `app.templates.words()` falls back to the
template that shares the metric shape. Steps 2 and 3 are now a template folder plus a `Template` literal
entry. Steps 4 and 5 are the first ones that change the referee and the value model, so they wait for the
value-model rework to land.

## 5. Dataset license summary

| Dataset | Rows | License | Status |
|---|---|---|---|
| UCI Bank Marketing (222) | 45,211 | CC BY 4.0 | fetch |
| UCI Default of Credit Card Clients (350) | 30,000 | CC BY 4.0 | fetch |
| UCI AI4I 2020 (601) | 10,000 | CC BY 4.0 | fetch |
| UCI Diabetes 130-US hospitals (296) | 101,766 | CC BY 4.0 | fetch |
| UCI Bike Sharing (275) | 17,379 | CC BY 4.0 | fetch |
| Hillstrom MineThatData | 64,000 | research use, confirm redistribution | confirm |
| OpenML freMTPL2 | 678,013 | confirm | confirm |
| Criteo Uplift | 13.9M | CC BY-NC-SA 4.0 | not for commercial demo |
| Kaggle credit, insurance, retail competitions | various | competition terms | avoid |

Every fetched dataset gets a `SOURCE.md` next to it in the same format as the fraud and churn ones.
