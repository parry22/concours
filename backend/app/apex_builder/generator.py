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
from app.packager.protect import sha256_file
from app.shared.metrics import METRIC_NAMES
from app.shared.translate import business_card

TEMPLATES = Path(__file__).parent / "templates"
ZERO = "sha256:" + "0" * 64
env = Environment(loader=FileSystemLoader(str(TEMPLATES)), autoescape=select_autoescape(default=False), keep_trailing_newline=True)


def competition_id(row: ProjectRow) -> str:
    return f"brief_{row.template}_{row.id}"[:64]


def task_description(spec: ProblemSpec, row: ProjectRow) -> str:
    if spec.business_template == "fraud":
        return f"Predict which rows are fraud (target `{spec.target_column}`) so that more fraud is caught at a fixed false-alarm budget."
    if spec.business_template == "churn":
        return f"Predict which customers will leave (target `{spec.target_column}`) so the riskiest can be contacted first."
    return f"Predict `{spec.target_column}` from the other columns."


def success_statement(spec: ProblemSpec) -> str:
    if spec.business_template == "fraud":
        return "A model the fraud team would switch on tomorrow: it catches clearly more fraud than today's rules at the same number of blocked good customers, and keeps doing so on next month's transactions."
    if spec.business_template == "churn":
        return "A ranking the retention team can act on: the customers it puts first really are the ones about to leave, and that holds on the next cohort."
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
        board = leaderboard.build(project_id, subs, spec, True)
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
    hidden = {f: report.checksums.get(f, sha256_file(comp / "referee" / "data" / f)) for f in HIDDEN_FILES}
    kept = [c for c in report.kept_columns]
    ctx = {
        "competition_id": cid,
        "version": "0.1.0",
        "display_name": f"{row.name} (Brief)",
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
        "metric_rationale": spec.metric_rationale or "chosen by Brief's metric policy from the positive rate",
        "split_strategy": "by time (oldest 70% train, next 10% leaderboard, newest 20% holdout)" if report.strategy == "time" else "stratified random 70/10/20, seed 42",
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
