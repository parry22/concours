"""Fairness report: for each sensitive column set aside by Protect, hit rate and selection rate per group.

Rows are the private holdout, scored by the active version (the same scores the value model reads). A row is
selected when it would make the list: the top k% for a top-k rule, the score threshold at the agreed false-alarm
rate for a fixed-FPR rule. Per group:

- selection rate: selected rows / rows in the group
- hit rate: selected rows that turned out positive / selected rows in the group
- base rate: positive rows / rows in the group, so a gap in selection can be read against a gap in need

The sensitive values never reach solvers: they live in `protected/<split>_sensitive.csv`, which staging does not
copy. Numeric columns (age) are grouped into fixed bands; a template may name coded values (`group_labels`).
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

from app.models import FairnessColumn, FairnessGroup, FairnessReport, ProblemSpec
from app.shared.metrics import threshold_at_fpr

MIN_GROUP_ROWS = 30  # smaller groups are reported but not judged
FOUR_FIFTHS = 0.8
AGE_BANDS = [0, 25, 35, 45, 55, 65, 200]
AGE_LABELS = ["Under 25", "25 to 34", "35 to 44", "45 to 54", "55 to 64", "65 and over"]


def sensitive_path(protected: Path, split: str) -> Path:
    return protected / f"{split}_sensitive.csv"


def selected_mask(y: np.ndarray, scores: np.ndarray, spec: ProblemSpec) -> np.ndarray:
    if spec.primary_metric == "recall_at_fpr":
        t = threshold_at_fpr(y, scores, float(spec.metric_params.get("fpr", 0.001)))
        return scores >= t
    top_k = float(spec.metric_params.get("top_k", 0.10))
    n = max(1, int(np.ceil(top_k * len(scores))))
    mask = np.zeros(len(scores), dtype=bool)
    mask[np.argsort(-scores, kind="stable")[:n]] = True
    return mask


def group_values(s: pd.Series, labels: dict[str, str] | None = None) -> pd.Series:
    if labels:
        return s.map(lambda v: labels.get(str(v), labels.get(str(v).split(".")[0], str(v))) if pd.notna(v) else "Not recorded")
    if pd.api.types.is_numeric_dtype(s) and s.nunique(dropna=True) > 12:
        return pd.cut(s, AGE_BANDS, labels=AGE_LABELS, right=False).astype(object).fillna("Not recorded").astype(str)
    # astype(str) keeps NaN on pandas 3, so fill first
    return s.astype(object).fillna("Not recorded").astype(str).replace({"nan": "Not recorded", "?": "Not recorded", "": "Not recorded"})


def column_report(column: str, trait: str, groups: pd.Series, y: np.ndarray, sel: np.ndarray) -> FairnessColumn:
    out: list[FairnessGroup] = []
    vals = groups.to_numpy()
    for g in sorted(set(vals), key=str):
        i = np.flatnonzero(vals == g)
        rows, chosen = len(i), int(sel[i].sum())
        hits = int((sel[i] & (y[i] == 1)).sum())
        out.append(FairnessGroup(
            group=str(g), rows=rows, positives=int(y[i].sum()), selected=chosen,
            selection_rate=round(chosen / rows, 4) if rows else 0.0,
            hit_rate=round(hits / chosen, 4) if chosen else None,
            base_rate=round(float(y[i].mean()), 4) if rows else 0.0,
            enough_rows=rows >= MIN_GROUP_ROWS,
        ))
    if trait == "age":  # bands read in order: "Under 25", "25 to 34" or "[20-30)"
        out.sort(key=lambda g: (g.group == "Not recorded", -1 if g.group.startswith("Under") else int(m.group()) if (m := re.search(r"\d+", g.group)) else 999))
    else:
        out.sort(key=lambda g: (g.group == "Not recorded", -g.rows))
    judged = [g for g in out if g.enough_rows and g.group != "Not recorded"]
    ratio, note = None, None
    if len(judged) >= 2:
        hi = max(judged, key=lambda g: g.selection_rate)
        lo = min(judged, key=lambda g: g.selection_rate)
        ratio = round(lo.selection_rate / hi.selection_rate, 3) if hi.selection_rate else None
        if ratio is not None and ratio < FOUR_FIFTHS:
            need = "which matches a lower rate of the outcome in that group" if lo.base_rate < hi.base_rate else "even though the outcome is not rarer in that group"
            note = (f"{lo.group} is put on the list at {ratio:.0%} of the rate for {hi.group}, {need}. "
                    "Check the gap is explained by real differences before acting on the list.")
        else:
            note = "Every group with enough rows is put on the list at four fifths or more of the highest group's rate."
    return FairnessColumn(column=column, trait=trait, groups=out, min_selection_ratio=ratio, note=note)


def report(protected: Path, spec: ProblemSpec, scores: np.ndarray, y: np.ndarray, traits: dict[str, str],
           group_labels: dict[str, dict[str, str]] | None = None, *, model_version: int | None = None) -> FairnessReport | None:
    p = sensitive_path(protected, "holdout")
    if not p.exists() or not traits:
        return None
    side = pd.read_csv(p, low_memory=False)
    if len(side) != len(scores):
        return None
    sel = selected_mask(y, scores, spec)
    cols = [column_report(c, traits.get(c, c), group_values(side[c], (group_labels or {}).get(c)).reset_index(drop=True), y, sel)
            for c in side.columns if c in traits]
    return FairnessReport(
        model_version=model_version, split="holdout", rows=int(len(scores)), selected=int(sel.sum()),
        rule=("top_k" if spec.primary_metric != "recall_at_fpr" else "fpr"), columns=cols,
    )


def for_project(s, row) -> FairnessReport | None:
    """The fairness report for a project's active version, or None before v1 or when nothing was set aside."""
    from app.config import project_dir  # noqa: PLC0415 - keep the packager importable without the app layers
    from app.models import SubmissionRow  # noqa: PLC0415
    from app.models_registry.promotion import active_version  # noqa: PLC0415
    from app.templates import group_labels  # noqa: PLC0415
    from app.value.scores import labels, split_scores  # noqa: PLC0415

    spec, rep = row.spec(), row.protect()
    if not spec or not rep or not rep.set_aside_columns:
        return None
    v = active_version(s, row.id)
    sub = s.get(SubmissionRow, v.submission_id) if v and v.submission_id else None
    if sub is None:
        return None
    scores = split_scores(row.id, sub, spec, allow_refit=True)
    if not scores:
        return None
    traits = {f.column: str(f.evidence.get("trait", f.column)) for f in rep.findings if f.check == "sensitive" and f.column}
    return report(project_dir(row.id) / "protected", spec, scores["holdout"], labels(row.id, "holdout"), traits,
                  group_labels(row.template), model_version=v.version)
