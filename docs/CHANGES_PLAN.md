# Changes plan: Brief becomes Concours

Source: the repositioning prompt of 2026-10-28. Everything below is implemented in this pass unless marked
"skipped" with a reason. Internal identifiers keep the `brief_`/`BRIEF_` prefixes where a rename would break
the arena cache or `uv.lock` (see "Not renamed").

## Decisions taken before writing code

- **v1 rule.** After Protect the backend runs `baseline_logreg` and `lgbm_default` through the arena (cached
  replays take seconds), picks the better private holdout score and stores it as model version 1, source
  `baseline`. Measured on the shipped data: fraud v1 = baseline_logreg (22%), churn v1 = lgbm_default (64%),
  leads v1 = lgbm_default (44%).
- **Promotion.** A scored submission is promoted when its private holdout score beats the active version by
  `project.min_improvement` (default 1% relative). Public scores never promote. Lower-is-better metrics
  (`wape`, `mae`) invert the comparison.
- **Two new local solvers** (`lgbm_regularized`, `lgbm_ensemble`) so the Improve round has more than one
  attempt after v1. Measured on leads: v1 0.4405, lgbm_regularized 0.4461 (promoted, v2), lgbm_ensemble
  0.4480 (0.4% over v2, not promoted). Ten other variants were tried; none clears 1% over 0.4461. The seed
  therefore gives "Inbound leads, November" v2 at Launch, not the v3 the prompt asks for. Faking a third
  version would need a number not produced by code. Fraud: v1 0.2156, lgbm_tuned 0.3015 (v2).
- **Finalize goes away as a user action.** The referee scores the private holdout on every run, so promotion
  happens as attempts arrive; the Improve screen shows business value from the private score, the public raw
  score is secondary. `project.finalized` stays in the DB for compatibility and is set when a round completes.
- **Lists** replace "score a CSV". A list is scored with the active version's solver, ranked by score, cut at
  the template's `top_n`, stored under `workspace/<pid>/lists/` with the version id and timestamp.
- **Health** is one endpoint: upload labeled rows, score with the active version, compare the primary metric
  with the version's holdout score, relative drop over `drift_threshold` (default 10%) sets `health=slipping`.
- **Pricing.** Bounty slider removed. `GET /projects/{id}/plan` returns an illustrative subscription and a
  success fee computed from the measured improvement over v1 (value model uplift where available). The
  suggested contest reward is computed in the same module and rendered only into HANDOFF.md.
- **Theme.** Kept as it was (the owner's call, 2026-10-28): the dark theme, gradient accents, cylinder logo and
  chart. Section 4.4 of the prompt (light editorial theme, serif display face) was not applied; only the layout,
  screens and copy changed.
- **Copy lint.** `frontend/lib/copy.ts` holds the strings; `frontend/scripts/copy-lint.mjs` (run by
  `pnpm test` and `make test`) fails on bounty, reward, TAO, subnet, miner, emission, LightGBM, XGBoost,
  logistic anywhere under `frontend/app`, `frontend/components`, `frontend/lib` except `lib/technical.ts`
  (algorithm labels for the technical drawer). "Apex" is allowed only in `launch/page.tsx` and in the
  `tooltips`/`launch` sections of `copy.ts`.

## Files

### Backend
| File | Change |
|---|---|
| `backend/app/models.py` | `Stage` becomes upload, intake, protect, model, improve, launch. New `ModelVersionRow`/`ModelVersionOut`, `ListRow`/`ListOut`, `HealthOut`, `PlanOut`, `ProjectSettingsIn`. `ProjectRow` gains `active_model_id`, `min_improvement`, `drift_threshold`, `health`, `health_json`, `refresh_daily`. `ProjectOut` gains `active_model`, `versions`, `current_result`, `improvement_line`, `health`, `health_check`, `model_status`, `refresh_daily`, `min_improvement`, `drift_threshold`, `list_name`. |
| `backend/app/db.py` | Add missing columns to an existing SQLite file and map legacy stage names (`arena`, `serve`) to the new ones. |
| `backend/app/config.py` | `DEFAULT_MIN_IMPROVEMENT`, `DEFAULT_DRIFT_THRESHOLD`, env names accept `CONCOURS_*` with `BRIEF_*` as fallback. |
| `backend/app/models_registry/__init__.py`, `promotion.py`, `lists.py`, `health.py`, `plan.py` | New package: version registry and promotion rules, list building, health check, improvement plan and suggested reward. |
| `backend/app/shared/translate.py` | `headline`, `improvement_line`, `result_short`, `metric_label`. |
| `backend/app/arena/service.py` | Runs carry a purpose (`baseline` or `contest`); promotion hooks after each scored submission and at run end; SSE events `model_version` and `model_promoted`. |
| `backend/app/arena/agent_solver.py` | Promotion hook after each scored attempt; rename in the system prompt. |
| `backend/app/arena/runner.py` | Two more solvers; image tags `concours-*`. |
| `backend/app/arena/leaderboard.py` | Business value per row from the private score; baseline for the card is v1's submission. |
| `backend/app/value/service.py` | `report_for` takes `baseline_solver` so the uplift is measured against v1. |
| `backend/solvers/lgbm_regularized/submission.py`, `backend/solvers/lgbm_ensemble/submission.py` | New local solvers. |
| `backend/app/main.py` | New stages; Protect starts the baseline run; endpoints `GET /projects/{id}/versions`, `POST/GET /projects/{id}/lists`, `GET /projects/{id}/lists/{lid}`, `GET /projects/{id}/lists/{lid}/download`, `POST /projects/{id}/health`, `PUT /projects/{id}/settings`, `GET /projects/{id}/plan`, `GET /projects/{id}/sample-csv?labeled=1&degrade=1`. `POST /projects/{id}/score` removed (Lists replace it). Title and handoff file name renamed. |
| `backend/app/apex_builder/generator.py` + `templates/*.j2` | Rename, `display_name`, suggested reward and `min_improvement` in HANDOFF.md section 3. |
| `backend/app/intake/prompts.py`, `backend/app/llm.py`, `backend/app/apex_builder/validate.py`, `backend/app/serving/score.py` | Rename in prompts and docstrings. |
| `backend/tests/test_promotion.py`, `test_lists_health.py`, `test_translate.py` | New. `test_templates.py` checks list framing. |
| `data/templates/{fraud,churn,leads}/defaults.json` | Card copy from the prompt, `list` framing block. |
| `scripts/seed.py`, `scripts/demo.sh`, `scripts/dev.sh`, `Makefile`, `docker-compose.yml`, `.env.example` | Three named seed projects; rename. |

### Frontend
| File | Change |
|---|---|
| `frontend/lib/copy.ts` (new) | All user-facing strings. |
| `frontend/lib/technical.ts` (new) | Algorithm labels, used only by the technical details drawer. |
| `frontend/scripts/copy-lint.mjs` (new), `frontend/package.json` | Lint script; `pnpm test` runs it. |
| `frontend/app/layout.tsx`, `frontend/app/icon.svg` | Title and description from `copy.ts`; the icon keeps the cylinder mark. `globals.css` unchanged. |
| `frontend/components/ui.tsx` | `StatusPill`, `ResultFigure`, `Badge` tooltip, `Stat` accent; the design tokens and the `Logo` mark are unchanged. |
| `frontend/components/ProjectShell.tsx` | New phases and steps, Lists link from step 4, version pill, rename. |
| `frontend/components/ValuePanel.tsx` | Strings from `copy.ts`; compares against your first model. |
| `frontend/lib/stages.ts`, `lib/api.ts`, `lib/api-types.ts` (regenerated), `lib/sse.ts`, `lib/format.ts` | New stages and endpoints. |
| `frontend/app/page.tsx` | Dashboard per 4.2. |
| `frontend/app/projects/[id]/upload`, `intake`, `protect` | Copy; Protect shows the v1 build and the "Your model v1 is ready" moment. |
| `frontend/app/projects/[id]/model/page.tsx` (new, replaces `serve`) | Top card, version timeline, health banner and check, technical details drawer, link to Lists. |
| `frontend/app/projects/[id]/lists/page.tsx` (new) | Ranked list, top N, action label, download, version and timestamp, refresh toggle. |
| `frontend/app/projects/[id]/improve/page.tsx` (new, replaces `arena`) | Improvement attempts, promotion moment, value panel. |
| `frontend/app/projects/[id]/launch/page.tsx` | Improvement plan, terms, handoff; the only screen that explains Apex. |
| `frontend/app/projects/[id]/page.tsx` | Redirect to the reached step. |

### Docs
`README.md`, `CONCOURS.md` (new; the repo never had `BRIEF.md`, the product brief lived outside it),
`docs/DEMO_SCRIPT.md`, `docs/UX_FLOW.md`, `docs/VALUE_MODEL.md`, `docs/APEX_CONTRACT.md`,
`docs/MODELLING_PLAN.md`, `data/templates/fraud/SOURCE.md`: rename and the new flow.

## Not renamed (cheap-and-safe rule)
- `backend/player/launch.py` and `backend/solvers/common/*` are part of the solver hash that keys the arena
  cache; touching them would force every cached run to re-execute in Docker. `BriefPlayer` stays.
- `pyproject.toml` package name stays `brief-backend` because `uv.lock` pins it (`uv sync --frozen`).
- `BRIEF_*` environment variables keep working; `CONCOURS_*` is read first.
- `brief_sub_*` module names in `serving/score.py` are pickled into cached fitted models.
