"""Generate the Apex competition package in workspace/<pid>/competition/ from the staged folder."""
from __future__ import annotations

import math
import shutil
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlmodel import select

from app.arena import leaderboard, runner
from app.arena.stage import HIDDEN_FILES, competition_dir, stage
from app.config import SOLVER_CPUS, SOLVER_TIMEOUT_S, project_dir
from app.db import session
from app.models import ProblemSpec, ProjectRow, SubmissionRow
from app.models_registry import plan as plan_mod
from app.models_registry import promotion
from app.packager.protect import sha256_file
from app.shared.metrics import METRIC_NAMES
from app.shared.translate import business_card
from app.templates import words

TEMPLATES = Path(__file__).parent / "templates"
ZERO = "sha256:" + "0" * 64
env = Environment(loader=FileSystemLoader(str(TEMPLATES)), autoescape=select_autoescape(default=False), keep_trailing_newline=True)


def competition_id(row: ProjectRow) -> str:
    return f"concours_{row.template}_{row.id}"[:64]


def fraud_handoff(row, report) -> dict | None:
    """Fraud settings, the embargo and the promotion gates, for HANDOFF.md section 1."""
    from app.config import AMOUNT_BANDS, GATE_RESAMPLES, GATE_SECONDS_PER_10K, GATE_SEGMENT_DROP, GATE_WIN_SHARE  # noqa: PLC0415

    st = row.fraud_settings() if hasattr(row, "fraud_settings") else None
    m = report.maturity
    if st is None or m is None:
        return None
    lo, hi = AMOUNT_BANDS
    return {
        "capacity": st.daily_capacity, "review_cost": f"{st.review_cost:,.2f}", "fee": f"{st.fraud_fee:,.2f}", "delay": st.label_delay_days,
        "as_of": m.as_of, "train_end": m.train_end, "embargo": f"{m.embargo_start} to {m.embargo_end}",
        "leaderboard": f"{m.leaderboard_start} to {m.holdout_start}", "holdout": f"{m.holdout_start} to {m.holdout_end}",
        "simulated": m.label_time_simulated, "unconfirmed_train": m.frauds_unconfirmed_in_train, "unconfirmed_eval": m.frauds_unconfirmed_at_eval,
        "resamples": GATE_RESAMPLES, "win_share": f"{GATE_WIN_SHARE:.0%}", "segment_drop": f"{GATE_SEGMENT_DROP:.0%}",
        "bands": f"under {lo:g}, {lo:g} to {hi:g}, over {hi:g}", "speed": f"{GATE_SECONDS_PER_10K:g}",
        "hashed": ", ".join(report.hashed_columns) or "none",
    }


def task_description(spec: ProblemSpec, row: ProjectRow) -> str:
    w = words(spec.template, spec.business_template)
    if spec.primary_metric == "fraud_amount_per_day":
        cap = spec.metric_params.get("capacity", 200)
        return (f"Score each payment's chance of fraud (target `{spec.target_column}`). Every day the {cap} payments with the highest "
                "expected loss (score x amount) go to the fraud team; the more fraud money inside those cases, the better.")
    if spec.business_template == "fraud":
        return f"Predict which rows are {w['short']} (target `{spec.target_column}`) so that more {w['short']} is caught at a fixed false-alarm budget."
    if spec.business_template == "churn":
        return f"Predict which {w['future']} (target `{spec.target_column}`) so the riskiest can be contacted first."
    return f"Predict `{spec.target_column}` from the other columns."


def success_statement(spec: ProblemSpec) -> str:
    w = words(spec.template, spec.business_template)
    if spec.primary_metric == "fraud_amount_per_day":
        return ("A daily review queue that holds more fraud money than today's model, day after day, including after fraudsters change "
                "tactics, without dropping any amount band or new customers.")
    if spec.business_template == "fraud":
        return f"A model the {w['team']} would switch on tomorrow: it catches clearly more {w['short']} than today's rules at the same number of blocked good customers, and keeps doing so on next month's transactions."
    if spec.business_template == "churn":
        return f"A ranking the {w['team']} can act on: the {w['negative']} it puts first really are the ones {w['about_to']}, and that holds on the next cohort."
    return "A model that improves on the baseline on fresh data and is simple enough to run inside the owner's systems."


def _mem(mem: str) -> str:
    return mem.replace("g", "Gi").replace("m", "Mi") if not mem.endswith(("Gi", "Mi")) else mem


def generate(project_id: str, *, validation: dict | None = None) -> tuple[Path, dict]:
    """Write spec.yaml, input.schema.json, README.md, HANDOFF.md, ONBOARDING_ISSUE.md, release.yml. Returns (dir, context)."""
    with session() as s:
        row = s.get(ProjectRow, project_id)
        spec = row.spec()
        report = row.protect()
        subs = s.exec(select(SubmissionRow).where(SubmissionRow.project_id == project_id).order_by(SubmissionRow.created_at)).all()
        versions = promotion.versions_for(s, project_id)
        v1 = next((v for v in versions if v.version == 1), None)
        active = next((v for v in versions if v.status == "active"), None)
        board = leaderboard.build(project_id, subs, spec, True, v1_submission_id=v1.submission_id if v1 else None, v1_solver=v1.solver_name if v1 else None)
        suggested_reward = plan_mod.suggested_reward(s, row)
        min_improvement = row.min_improvement
    comp = stage(project_id, spec) if not (competition_dir(project_id) / "player" / "launch.py").exists() else competition_dir(project_id)
    cid = competition_id(row)
    parts = {p.name: p for p in report.parts}
    train_rows, lb_rows, ho_rows = parts["train"].rows, parts["leaderboard"].rows, parts["holdout"].rows
    best = board.leader
    base = board.baseline
    eval_s = (best.eval_seconds if best and best.eval_seconds else 120.0)
    n_batches = math.ceil(lb_rows / 5000) + math.ceil(ho_rows / 5000)
    worst = int(eval_s + n_batches * 60 + 30)
    referee_timeout = max(900, min(7200, worst * 2))
    evaluate_timeout = referee_timeout
    validation = validation or {}
    player_digest = runner.image_id(project_id, "player") or ZERO
    referee_digest = runner.image_id(project_id, "referee") or ZERO
    hidden = {f: report.checksums.get(f) or sha256_file(comp / "referee" / "data" / f) for f in HIDDEN_FILES
              if f in report.checksums or (comp / "referee" / "data" / f).exists()}
    kept = [c for c in report.kept_columns]
    ctx = {
        "competition_id": cid,
        "version": "0.1.0",
        "display_name": f"{row.name} (Concours)",
        "date": date.today().isoformat(),
        "cpu_limit": int(SOLVER_CPUS) if float(SOLVER_CPUS).is_integer() else SOLVER_CPUS,
        "mem_limit": "2Gi",
        "image_ref": f"ghcr.io/your-org/{cid.replace('_', '-')}-player",
        "referee_ref": f"ghcr.io/your-org/{cid.replace('_', '-')}-referee",
        "player_digest": player_digest,
        "referee_digest": referee_digest,
        "reveal_days": 7,
        "evaluate_timeout_s": evaluate_timeout,
        "referee_timeout_s": referee_timeout,
        "cosign_identity": f"https://github.com/your-org/{cid.replace('_', '-')}/.github/workflows/release.yml",
        "task_description": task_description(spec, row),
        "success_statement": success_statement(spec),
        "metric_name": METRIC_NAMES.get(spec.primary_metric, spec.primary_metric),
        "metric_params": ", ".join(f"{k}={v}" for k, v in spec.metric_params.items()),
        "secondary_name": METRIC_NAMES.get(spec.secondary_metric or "", spec.secondary_metric or "none"),
        "metric_rationale": spec.metric_rationale or "chosen by Concours's metric policy from the positive rate",
        "fraud": fraud_handoff(row, report),
        "split_strategy": {
            "time_embargo": "by time with an embargo: train, a gap of label_delay_days, a leaderboard window, then the holdout window (see the fraud section)",
            "time": "by time (oldest 70% train, next 10% leaderboard, newest 20% holdout)",
            "group": f"by {report.group_column} 70/10/20, seed 42: every row of one {report.group_column} sits in one part",
        }.get(report.strategy, "stratified random 70/10/20, seed 42"),
        "train_rows": train_rows,
        "lb_rows": lb_rows,
        "holdout_rows": ho_rows,
        "holdout_positives": parts["holdout"].positives,
        "feature_columns": ", ".join(kept),
        "time_column": spec.time_column or "none",
        "n_findings": len(report.findings),
        "dropped": ", ".join(report.dropped_columns) or "none",
        "masked": ", ".join(report.masked_columns) or "none",
        "rows_removed": report.rows_removed,
        "baseline_private": f"{base.private_score:.4f}" if base and base.private_score is not None else "not run",
        "best_private": f"{best.private_score:.4f}" if best and best.private_score is not None else "not run",
        "best_solver": best.solver if best else "none",
        "business_card": board.business_card or "",
        "v1_line": f"v{v1.version} ({v1.solver_name}, {v1.private_score:.4f})" if v1 else "not built",
        "active_line": f"v{active.version} ({active.solver_name}, {active.private_score:.4f})" if active else "not built",
        "n_versions": len(versions),
        "min_improvement_pct": f"{min_improvement * 100:g}%",
        "suggested_reward": f"${suggested_reward:,.0f}",
        "takeover_margin": f"{best.private_score * 0.01:.4f}" if best and best.private_score else "n/a",
        "eval_seconds": f"{eval_s:.0f}",
        "n_batches": n_batches,
        "worst_case_s": worst,
        "fits": "yes" if worst < referee_timeout else "NO",
        "hidden_checksums": hidden,
        "checksums": report.checksums,
        "preflight_status": validation.get("preflight", "not run"),
        "preflight_box": "☑" if validation.get("preflight") == "pass" else "☐",
        "local_run_status": validation.get("local_run", "not run"),
        "local_run_detail": validation.get("local_run_detail", ""),
        "local_run_box": "☑" if validation.get("local_run") == "pass" else "☐",
        "local_run_x": "x" if validation.get("local_run") == "pass" else " ",
    }
    (comp / "spec.yaml").write_text(env.get_template("spec.yaml.j2").render(ctx))
    shutil.copyfile(TEMPLATES / "input.schema.json", comp / "input.schema.json")
    (comp / "README.md").write_text(env.get_template("README.md.j2").render(ctx))
    (comp / "HANDOFF.md").write_text(env.get_template("HANDOFF.md.j2").render(ctx))
    (comp / "ONBOARDING_ISSUE.md").write_text(env.get_template("ONBOARDING_ISSUE.md.j2").render(ctx))
    wf = comp / ".github" / "workflows"
    wf.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(TEMPLATES / "release.yml", wf / "release.yml")
    (comp / ".gitignore").write_text("out/\n__pycache__/\n")
    shutil.copyfile(project_dir(project_id) / "protected" / "leakage_report.json", comp / "leakage_report.json")
    return comp, ctx


def file_list(comp: Path) -> list[str]:
    return sorted(str(p.relative_to(comp)) for p in comp.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
