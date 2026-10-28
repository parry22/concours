"""Fraud project flow: schema confirmation, settings, protection on the current window, today's queue, analyst
verdicts, the weekly health and drift check, and the simulated clock ("jump forward")."""
from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sqlmodel import Session, select

from app.config import FRAUD_DEFAULTS, HEALTH_DROP, PSI_LIMIT, SAMPLE_AS_OF_DAY, project_dir
from app.models import (
    CaseLabelRow, DriftFeature, DriftOut, FraudSettings, ModelVersionRow, ProblemSpec, ProjectRow, ProtectReport, QueueCase,
    QueueOut, QueueReason, SubmissionRow, WeekHealth,
)
from app.fraud import reasons as reasons_mod
from app.fraud.labels import known_label, windows
from app.fraud.protect import hash_ids, protect_fraud
from app import secure_store
from app.fraud.schema import canonical, drop_card_columns, read_canonical, write_canonical
from app.shared.metrics import fraud_queue

WEEK = 7


# ---------- settings and spec ----------


def settings_of(row: ProjectRow) -> FraudSettings:
    return row.fraud_settings() or FraudSettings(**FRAUD_DEFAULTS)


def spec_for(st: FraudSettings) -> ProblemSpec:
    return ProblemSpec(
        template="fraud", target_column="is_fraud", positive_label=1, time_column="transaction_time",
        primary_metric="fraud_amount_per_day",
        metric_params={"capacity": st.daily_capacity, "fee": st.fraud_fee, "review_cost": st.review_cost},
        secondary_metric="pr_auc", business_template="fraud",
        metric_rationale=(f"Your team reviews {st.daily_capacity} cases a day, so every model is judged on the fraud money inside "
                          "those cases, day by day, on the newest weeks whose labels have had time to arrive."),
    )


def is_fraud_project(row: ProjectRow) -> bool:
    return row.template == "fraud" and row.mapping_json is not None


# ---------- files ----------


def raw_path(pid: str) -> Path:
    return project_dir(pid) / "raw.csv"


def dataset_path(pid: str) -> Path:
    return project_dir(pid) / "dataset.csv"


def private_dir(pid: str) -> Path:
    d = project_dir(pid) / "private"
    d.mkdir(exist_ok=True)
    return d


def confirm_schema(row: ProjectRow, mapping: dict[str, str | None], *, sample: bool) -> pd.DataFrame:
    raw = secure_store.read_csv(raw_path(row.id), low_memory=False)
    raw, cards = drop_card_columns(raw, mapping)
    df, simulated = canonical(raw, {k: v for k, v in mapping.items() if v})
    write_canonical(df, dataset_path(row.id))
    # the upload is no longer needed: only its column names stay, for the mapping screen
    (private_dir(row.id) / "columns.json").write_text(json.dumps({"columns": [str(c) for c in raw.columns], "dropped_cards": cards}))
    raw_path(row.id).unlink(missing_ok=True)
    first, last = df["transaction_time"].min().normalize(), df["transaction_time"].max().normalize()
    span = (last - first).days + 1
    as_of = first + pd.Timedelta(days=SAMPLE_AS_OF_DAY - 1) if sample and span > SAMPLE_AS_OF_DAY else last
    row.mapping_json = json.dumps({k: v for k, v in mapping.items() if v})
    row.data_end = last.strftime("%Y-%m-%d")
    row.as_of = as_of.strftime("%Y-%m-%d")
    row.salt = row.salt or secrets.token_hex(16)
    (private_dir(row.id) / "label_time.json").write_text(json.dumps({"simulated": simulated}))
    if row.fraud_settings_json is None:
        row.fraud_settings_json = FraudSettings(**FRAUD_DEFAULTS).model_dump_json()
    row.set_spec(spec_for(settings_of(row)))
    return df


def label_time_simulated(pid: str) -> bool:
    f = private_dir(pid) / "label_time.json"
    return bool(json.loads(f.read_text()).get("simulated")) if f.exists() else True


def analyst_labels(s: Session, pid: str) -> dict[str, tuple[int, str]]:
    rows = s.exec(select(CaseLabelRow).where(CaseLabelRow.project_id == pid).order_by(CaseLabelRow.created_at)).all()
    return {r.transaction_id: (r.label, r.label_time) for r in rows}


def run_protect(s: Session, row: ProjectRow) -> ProtectReport:
    df = read_canonical(dataset_path(row.id))
    report, _, _ = protect_fraud(df, settings_of(row), row.as_of, row.salt or "", project_dir(row.id) / "protected", private_dir(row.id),
                                 simulated=label_time_simulated(row.id), analyst_labels=analyst_labels(s, row.id))
    row.protect_json = report.model_dump_json()
    return report


def window_moved(row: ProjectRow) -> bool:
    rep = row.protect()
    return bool(rep and rep.maturity and row.as_of and rep.maturity.as_of != row.as_of)


# ---------- scoring with the active version ----------


def _hashed(df: pd.DataFrame, salt: str) -> pd.DataFrame:
    out = df.copy()
    for c in ("customer_id", "merchant_or_terminal_id"):
        if c in out.columns:
            out[c] = hash_ids(out[c], salt)[0]
    return out


def score_window(pid: str, version: ModelVersionRow, spec: ProblemSpec, frame: pd.DataFrame) -> tuple[object, pd.DataFrame, np.ndarray]:
    """Score a time-ordered frame of hashed canonical rows with the version's solver (fit on the current train split)."""
    from app.packager.transform import Transform  # noqa: PLC0415
    from app.serving.score import fitted_model  # noqa: PLC0415
    from app.value.scores import submission_path  # noqa: PLC0415

    transform = Transform.load(project_dir(pid) / "protected" / "transform.json")
    feats = transform.apply(frame.drop(columns=[c for c in ("is_fraud",) if c in frame.columns])).reset_index(drop=True)
    model, _ = fitted_model(pid, version.solver_name, spec, submission_path=submission_path(pid, version.solver_name))
    if hasattr(model, "buffer"):
        model.buffer = None  # velocity history comes from this frame, not from an earlier scoring call
    scores = np.asarray(model.score_frame(feats), dtype=float)
    return model, feats, scores


# ---------- today's review queue ----------


def queue_dir(pid: str) -> Path:
    d = project_dir(pid) / "queue"
    d.mkdir(exist_ok=True)
    return d


def build_queue(s: Session, row: ProjectRow, version: ModelVersionRow) -> QueueOut:
    st, spec = settings_of(row), row.spec()
    cache = queue_dir(row.id) / f"{row.as_of}-v{version.version}-{version.id}.json"
    if cache.exists():
        q = QueueOut.model_validate_json(cache.read_text())
    else:
        recent = secure_store.read_csv(private_dir(row.id) / "recent.csv", low_memory=False, dtype={"transaction_id": str})
        recent["transaction_time"] = pd.to_datetime(recent["transaction_time"])
        recent = recent.sort_values("transaction_time", kind="stable").reset_index(drop=True)
        day = pd.Timestamp(row.as_of)
        start = day - pd.Timedelta(days=3)  # three days of history for velocity, today is scored
        frame = recent[recent["transaction_time"] >= start].reset_index(drop=True)
        model, feats, scores = score_window(row.id, version, spec, frame)
        today = np.flatnonzero((frame["transaction_time"] >= day).to_numpy())
        amt = frame["amount"].to_numpy(dtype=float)
        el = scores * (amt + st.fraud_fee)
        pick = today[np.argsort(-el[today], kind="stable")[: st.daily_capacity]]
        why = reasons_mod.explain(model, feats, pick)
        cases = [
            QueueCase(rank=i + 1, transaction_id=str(frame.at[j, "transaction_id"]),
                      time=frame.at[j, "transaction_time"].strftime("%Y-%m-%d %H:%M"), amount=round(float(amt[j]), 2),
                      customer=f"{int(frame.at[j, 'customer_id']):x}"[:10] if "customer_id" in frame.columns else "",
                      risk=round(float(scores[j]), 4), expected_loss=round(float(el[j]), 2),
                      reasons=[QueueReason(text=t, weight=w) for t, w in why[i]])
            for i, j in enumerate(pick)
        ]
        q = QueueOut(day=row.as_of, model_version=version.version, capacity=st.daily_capacity, rows_scored=int(len(today)),
                     cases=cases, expected_loss_total=round(float(el[pick].sum()), 2), labeled=0, created_at=datetime.now(timezone.utc))
        cache.write_text(q.model_dump_json())
    labels = {r.transaction_id: r.label for r in s.exec(select(CaseLabelRow).where(CaseLabelRow.project_id == row.id)).all()}
    for c in q.cases:
        lab = labels.get(c.transaction_id)
        c.label = None if lab is None else ("fraud" if lab == 1 else "not_fraud")
    q.labeled = sum(1 for c in q.cases if c.label)
    return q


def set_label(s: Session, row: ProjectRow, transaction_id: str, label: str | None, version: int) -> None:
    old = s.exec(select(CaseLabelRow).where(CaseLabelRow.project_id == row.id, CaseLabelRow.transaction_id == transaction_id)).all()
    for r in old:
        s.delete(r)
    if label is not None:
        # dated with the simulated now: the verdict is known from today, as a chargeback would be
        s.add(CaseLabelRow(project_id=row.id, transaction_id=transaction_id, label=1 if label == "fraud" else 0,
                           label_time=f"{row.as_of} 23:59:59", model_version=version))
    s.commit()


def queue_csv(q: QueueOut) -> str:
    rows = [{"rank": c.rank, "transaction_id": c.transaction_id, "time": c.time, "amount": c.amount, "customer": c.customer,
             "risk_score": c.risk, "expected_loss": c.expected_loss,
             **{f"reason_{i + 1}": (c.reasons[i].text if i < len(c.reasons) else "") for i in range(3)},
             "analyst_label": c.label or ""} for c in q.cases]
    return pd.DataFrame(rows).to_csv(index=False)


# ---------- health and drift ----------


def psi(base: np.ndarray, cur: np.ndarray, bins: int = 10) -> float:
    """Population stability index with quantile bins from the baseline."""
    base, cur = np.asarray(base, dtype=float), np.asarray(cur, dtype=float)
    if len(base) == 0 or len(cur) == 0:
        return 0.0
    edges = np.unique(np.quantile(base, np.linspace(0, 1, bins + 1)))
    if len(edges) < 3:
        return 0.0
    edges[0], edges[-1] = -np.inf, np.inf
    b = np.histogram(base, edges)[0] / len(base)
    c = np.histogram(cur, edges)[0] / len(cur)
    b, c = np.clip(b, 1e-4, None), np.clip(c, 1e-4, None)
    return float(np.sum((c - b) * np.log(c / b)))


def _terminal_activity(df: pd.DataFrame) -> np.ndarray:
    """Per payment: how many payments its terminal took that day."""
    if "merchant_or_terminal_id" not in df.columns:
        return np.zeros(len(df))
    d = df["transaction_time"].dt.normalize()
    return df.groupby([df["merchant_or_terminal_id"], d])["amount"].transform("size").to_numpy(dtype=float)


def drift_features(base: pd.DataFrame, cur: pd.DataFrame) -> list[DriftFeature]:
    out = []
    for name, f in (("Amount", lambda x: x["amount"].to_numpy(dtype=float)),
                    ("Hour of day", lambda x: x["transaction_time"].dt.hour.to_numpy(dtype=float)),
                    ("Payments per terminal per day", _terminal_activity)):
        v = round(psi(f(base), f(cur)), 4)
        out.append(DriftFeature(name=name, psi=v, flagged=v > PSI_LIMIT))
    return out


def holdout_share(pid: str, sub: SubmissionRow, spec: ProblemSpec) -> float | None:
    """The version's share of fraud money caught on its holdout (the health baseline)."""
    from app.value.scores import labels, split_scores  # noqa: PLC0415

    sc = split_scores(pid, sub, spec, allow_refit=True)
    meta_p = project_dir(pid) / "protected" / "holdout_meta.csv"
    if not sc or not meta_p.exists():
        return None
    meta = pd.read_csv(meta_p)
    p = spec.metric_params
    q = fraud_queue(labels(pid, "holdout"), sc["holdout"], meta["amount"], meta["day"], int(p["capacity"]), float(p.get("fee", 0)),
                    float(p.get("review_cost", 0)))
    return q["share"]


def check(s: Session, row: ProjectRow, *, new_as_of: str | None = None) -> DriftOut:
    """Weekly health on mature labels and PSI drift, for the active version, at `new_as_of` (default: now).
    Weeks run from the day after the version's holdout to the newest day whose labels are mature."""
    from app.models_registry.promotion import active_version  # noqa: PLC0415

    st, spec, rep = settings_of(row), row.spec(), row.protect()
    as_of = new_as_of or row.as_of
    version = active_version(s, row.id)
    now = datetime.now(timezone.utc)
    if version is None or rep is None or rep.maturity is None:
        return DriftOut(as_of=as_of, model_version=None, baseline_share=None, weeks=[], psi=[], performance_drop=None, slipping=False,
                        reason="none", line="No model to watch yet.", checked_at=now)
    sub = s.get(SubmissionRow, version.submission_id) if version.submission_id else None
    base_share = holdout_share(row.id, sub, spec) if sub else None
    df = read_canonical(dataset_path(row.id))
    w_new = windows(as_of, st.label_delay_days)
    df = df[df["transaction_time"] < w_new.as_of_end]
    df = _hashed(df, row.salt or "")
    start = pd.Timestamp(rep.maturity.holdout_end) + pd.Timedelta(days=1)
    mature_end = w_new.immature_start  # first day without mature labels
    weeks: list[WeekHealth] = []
    if mature_end > start:
        span = df[(df["transaction_time"] >= start - pd.Timedelta(days=3)) & (df["transaction_time"] < mature_end)].reset_index(drop=True)
        if len(span):
            _, _, scores = score_window(row.id, version, spec, span.drop(columns=["label_time"]))
            y = known_label(span["is_fraud"], span["label_time"], w_new.as_of_end).to_numpy()
            keep = (span["transaction_time"] >= start).to_numpy()
            day = span["transaction_time"].dt.strftime("%Y-%m-%d").to_numpy()
            q = fraud_queue(y[keep], scores[keep], span["amount"].to_numpy()[keep], day[keep], st.daily_capacity, st.fraud_fee, st.review_cost)
            days = q["days"]
            for i in range(0, len(days) - WEEK + 1, WEEK):
                ca, fa = q["caught_amount_by_day"][i:i + WEEK], q["fraud_amount_by_day"][i:i + WEEK]
                share = float(ca.sum() / fa.sum()) if fa.sum() else 0.0
                drop = (base_share - share) / base_share if base_share else 0.0
                weeks.append(WeekHealth(week_start=days[i], week_end=days[i + WEEK - 1], caught_per_day=round(float(ca.mean()), 2),
                                        fraud_per_day=round(float(fa.mean()), 2), share=round(share, 4), drop=round(drop, 4)))
    train_end = pd.Timestamp(rep.maturity.train_end)
    base = df[df["transaction_time"] <= train_end + pd.Timedelta(days=1)]
    base = base[base["transaction_time"] > train_end - pd.Timedelta(days=28)]
    cur = df[df["transaction_time"] >= w_new.as_of - pd.Timedelta(days=WEEK - 1)]
    feats = drift_features(base, cur)
    perf_drop = weeks[-1].drop if weeks else None
    perf = perf_drop is not None and perf_drop > HEALTH_DROP
    drifted = any(f.flagged for f in feats)
    reason = "both" if perf and drifted else "performance" if perf else "drift" if drifted else "none"
    if perf:
        line = f"New fraud pattern detected. Your model is catching {perf_drop:.0%} less fraud."
    elif drifted:
        top = max(feats, key=lambda f: f.psi)
        line = f"Payments look different from the training data ({top.name.lower()} shifted, PSI {top.psi:.2f})."
    elif weeks:
        line = f"Healthy: catching {weeks[-1].share:.0%} of fraud money in the latest mature week, in line with {base_share:.0%} on the holdout."
    else:
        line = "No week has mature labels since the model was built yet."
    return DriftOut(as_of=as_of, model_version=version.version, baseline_share=round(base_share, 4) if base_share is not None else None,
                    weeks=weeks, psi=feats, performance_drop=perf_drop, slipping=perf or drifted, reason=reason, line=line, checked_at=now)


def jump(s: Session, row: ProjectRow, days: int) -> tuple[DriftOut, bool]:
    """Move the clock, check health on the newly mature weeks. Returns the check and whether the window moved."""
    new = min(pd.Timestamp(row.as_of) + pd.Timedelta(days=days), pd.Timestamp(row.data_end))
    new_iso = new.strftime("%Y-%m-%d")
    out = check(s, row, new_as_of=new_iso)
    moved = new_iso != row.as_of
    row.as_of = new_iso
    row.health = "slipping" if out.slipping else "healthy"
    row.drift_json = out.model_dump_json()
    row.updated_at = datetime.now(timezone.utc)
    return out, moved
