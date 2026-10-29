"""Lists: batch delivery. Score new rows with the active version, rank them, keep the top N, store with the version."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sqlmodel import Session, select

from app.config import project_dir
from app.models import ListOut, ListRow, ModelVersionRow, ProblemSpec, ProjectRow
from app.models_registry.promotion import list_framing
from app.packager.transform import Transform
from app.shared.csv_safe import safe_frame
from app.serving.score import fitted_model
from app.value.scores import submission_path

PREVIEW_ROWS = 25


def score_frame(project_id: str, version: ModelVersionRow, spec: ProblemSpec, df: pd.DataFrame) -> np.ndarray:
    """Scores for `df` from the version's solver (re-fit on the public train split, cached on disk)."""
    transform = Transform.load(project_dir(project_id) / "protected" / "transform.json")
    feats = transform.apply(df)  # raises ValueError naming the missing columns
    if transform.target_column in feats.columns:
        feats = feats.drop(columns=[transform.target_column])
    model, _ = fitted_model(project_id, version.solver_name, spec, submission_path=submission_path(project_id, version.solver_name))
    return np.asarray(model.score_frame(feats), dtype=float)


def build(s: Session, row: ProjectRow, version: ModelVersionRow, spec: ProblemSpec, src: Path, *, top_n: int | None = None) -> ListRow:
    framing = list_framing(row.template, spec)
    df = pd.read_csv(src, low_memory=False)
    if spec.target_column in df.columns:
        df = df.drop(columns=[spec.target_column])
    scores = score_frame(row.id, version, spec, df)
    n = int(top_n or framing["top_n"])
    out = df.copy()
    out.insert(0, "score", np.round(scores, 6))
    order = np.argsort(-scores, kind="stable")
    out = out.iloc[order].reset_index(drop=True)
    out.insert(0, "rank", np.arange(1, len(out) + 1))
    out.insert(2, "action", np.where(out["rank"] <= n, framing["action_label"], ""))
    lists_dir = project_dir(row.id) / "lists"
    lists_dir.mkdir(exist_ok=True)
    rec = ListRow(project_id=row.id, model_version_id=version.id, model_version=version.version, solver_name=version.solver_name,
                  name=framing["name"], rows_scored=int(len(out)), top_n=n, columns_json=json.dumps(list(out.columns)))
    rec.path = str(lists_dir / f"{rec.id}.csv")
    safe_frame(out).to_csv(rec.path, index=False)  # analysts open this in Excel: no formula cells
    s.add(rec)
    row.updated_at = datetime.now(timezone.utc)
    if row.stage in ("upload", "intake", "protect"):
        row.stage = "model"
    s.add(row)
    s.commit()
    s.refresh(rec)
    return rec


def _clean(v):
    if isinstance(v, float) and np.isnan(v):
        return None
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return float(v)
    return v


def to_out(rec: ListRow, template: str, spec: ProblemSpec | None, *, preview: bool = True) -> ListOut:
    framing = list_framing(template, spec)
    rows: list[dict] = []
    if preview and rec.path and Path(rec.path).exists():
        head = pd.read_csv(rec.path, nrows=min(PREVIEW_ROWS, max(rec.top_n, 1)))
        rows = [{k: _clean(v) for k, v in r.items()} for r in head.to_dict(orient="records")]
    return ListOut(
        id=rec.id, project_id=rec.project_id, name=rec.name, model_version=rec.model_version, model_version_id=rec.model_version_id,
        solver_name=rec.solver_name, rows_scored=rec.rows_scored, top_n=rec.top_n, row_label=framing["row_label"],
        action_label=framing["action_label"], columns=json.loads(rec.columns_json), preview=rows, created_at=rec.created_at,
        download=f"/projects/{rec.project_id}/lists/{rec.id}/download",
    )


def for_project(s: Session, project_id: str) -> list[ListRow]:
    return list(s.exec(select(ListRow).where(ListRow.project_id == project_id).order_by(ListRow.created_at.desc())).all())
