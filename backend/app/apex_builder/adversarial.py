"""Adversarial submission set (toolkit HANDOFF §5.3): degenerate submissions run through the local referee.

Each one goes through the same Docker flow as a solver (arena.runner.run_submission) against the project's built
player and referee images. Results land in workspace/<pid>/adversarial.json; the generator renders them into
HANDOFF.md §2 and §5 item 9, so the recorded scores always come from a run, never from hand-written text.

  .venv/bin/python -m app.apex_builder.adversarial <project_id>
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

from app.arena import runner
from app.arena.stage import competition_dir
from app.config import project_dir

_HEAD = '''"""Adversarial: {doc}"""
from __future__ import annotations

import numpy as np
import pandas as pd

from common.base import SolverBase


class Solver(SolverBase):
    name = "adversarial_{name}"

    def fit(self, X: pd.DataFrame, y: np.ndarray) -> None:
        self.rng = np.random.default_rng(0)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        return {body}
'''

# name -> (what it does, predict_proba body)
SUBMISSIONS = {
    "constant": ("the same score (0.5) for every payment", "np.full(len(X), 0.5)"),
    "random": ("uniform random scores, seed 0", "self.rng.random(len(X))"),
    "all_zeros": ("a score of 0 for every payment", "np.zeros(len(X))"),
}


def source(name: str) -> str:
    doc, body = SUBMISSIONS[name]
    return _HEAD.format(doc=doc, name=name, body=body)


def results_path(project_id: str) -> Path:
    return project_dir(project_id) / "adversarial.json"


def load(project_id: str) -> dict | None:
    p = results_path(project_id)
    return json.loads(p.read_text()) if p.exists() else None


def verdicts(results: dict, bar: float | None) -> list[dict]:
    """One line per submission for HANDOFF.md: score, share of the starting bar (spec `baseline_raw_score`), and whether
    it stays below that bar, so it can never take the lead."""
    out = []
    for r in results.get("submissions", []):
        score = r["raw_score"] if r["ok"] else 0.0
        share = score / bar if bar else None
        below = bar is not None and score < bar
        note = ""
        if r["name"] == "constant" and results.get("primary_metric") == "fraud_amount_per_day":
            note = ("Under fraud_amount_per_day a constant score ranks each day's payments by amount alone, so this "
                    "submission is the rule 'review the largest payments'. The metric is unchanged; the starting bar is "
                    "today's model, which this rule does not reach.")
        out.append({**r, "score": score, "share": share, "below": below, "note": note})
    return out


def run(project_id: str, log=print) -> dict:
    if runner.image_id(project_id, "player") is None or runner.image_id(project_id, "referee") is None:
        raise RuntimeError("build the player and referee images first (run the arena or build the package)")
    config = json.loads((competition_dir(project_id) / "fixtures" / "input.json").read_text())
    src_dir = project_dir(project_id) / "adversarial"
    src_dir.mkdir(exist_ok=True)
    rows = []
    for name, (doc, _) in SUBMISSIONS.items():
        path = src_dir / f"{name}.py"
        path.write_text(source(name))
        log(f"running {name}: {doc}")
        r = runner.run_submission(project_id, f"adversarial-{name}", name, config, submission_path=path)
        res = r.result or {}
        meta = res.get("metadata", {})
        holdout = meta.get("splits", {}).get("holdout", {})
        row = {
            "name": name,
            "description": doc,
            "ok": r.ok,
            "raw_score": res["raw_scores"][0] if r.ok else None,
            "public_score": meta.get("public_score"),
            "terminal_reason": res.get("terminal_reason"),
            "fraud": holdout.get("fraud"),
            "seconds": round(r.seconds, 1),
            "error": r.error,
        }
        log(f"  {name}: raw_score={row['raw_score']} terminal_reason={row['terminal_reason']} error={r.error}")
        rows.append(row)
    out = {"date": date.today().isoformat(), "primary_metric": config.get("primary_metric"),
           "metric_params": config.get("metric_params", {}), "submissions": rows}
    results_path(project_id).write_text(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python -m app.apex_builder.adversarial <project_id>")
    run(sys.argv[1])
