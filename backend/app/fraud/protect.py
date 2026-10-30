"""Fraud protection (Tier 1). Runs on the canonical dataset up to the as-of date.

1. Analyst verdicts from the review queue replace `is_fraud`, with `label_time` = when they were given.
2. customer_id and merchant_or_terminal_id become salted hashes (positive 63-bit integers, so solvers still see
   repeated entities). The mapping stays in `private/id_map.csv`, never staged.
3. Column checks: leaks (TX_FRAUD_SCENARIO), identifiers, card numbers (dropped), personal data, post-outcome
   names, constants, future information.
4. Windows with the embargo and label maturity (see fraud/labels.py).
5. Files: train.csv (features + label known at the cutoff), leaderboard/holdout features, labels known at the
   as-of date, and `<split>_meta.csv` (day, amount, new customer) for the capacity metric and the gates.
   The newest immature days go to `private/recent.csv` for today's queue and drift.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from app import secure_store
from app.models import FraudSettings, Finding, MaturitySummary, ProtectReport, SplitPart
from app.packager.checks import constant, future_info, id_like, pii, post_outcome_name, target_leak
from app.packager.checks.base import CheckContext
from app.packager.protect import sha256_file
from app.packager.transform import Transform
from app.shared.metrics import fraud_queue
from app.config import MIN_WINDOW_ROWS
from app.fraud.labels import Windows, check_room, label_parts, summary_counts, windows

HASHED = ("customer_id", "merchant_or_terminal_id")
NOT_FEATURES = {"is_fraud", "label_time", "part", "y_train", "y_eval"}
CHECK_SAMPLE = 400_000  # rows the column checks look at (seeded sample); the split itself uses every row
COLUMN_CHECKS = (id_like.run, pii.run, post_outcome_name.run, target_leak.run, constant.run, future_info.run)


def hash_ids(values: pd.Series, salt: str, *, keyed: bool = True) -> tuple[pd.Series, pd.DataFrame]:
    """BLAKE2b of each distinct value, as a positive 63-bit integer. Returns the hashed column and the map.
    `keyed` (protection version 2) uses the salt as the hash key, the keyed construction; version 1 prefixed it."""
    text = values.where(values.notna(), "nan").astype(str)  # blank IDs share one bucket, "nan", as version 1 always hashed them
    uniq = pd.unique(text)
    if keyed:
        key = hashlib.sha256(salt.encode()).digest()  # any salt length becomes a 32-byte key
        hashed = {u: int(hashlib.blake2b(u.encode(), key=key, digest_size=8).hexdigest(), 16) >> 1 for u in uniq}
    else:
        hashed = {u: int(hashlib.blake2b(f"{salt}:{u}".encode(), digest_size=8).hexdigest(), 16) >> 1 for u in uniq}
    out = text.map(hashed).astype("int64")
    return out, pd.DataFrame({"original": list(hashed.keys()), "hashed": list(hashed.values())})


def clock_counters(df: pd.DataFrame, features: list[str]) -> list[str]:
    """Numeric columns that rise with transaction time almost perfectly (a running clock, a day counter)."""
    t = df["transaction_time"].astype("int64").to_numpy()
    sample = np.linspace(0, len(df) - 1, min(len(df), 20000)).astype(int)
    out = []
    for c in features:
        if c in ("transaction_time", "amount", "transaction_id") or not pd.api.types.is_numeric_dtype(df[c]) or df[c].nunique() < 10:
            continue
        v = df[c].to_numpy()[sample]
        if np.isnan(v.astype(float)).any():
            continue
        r = np.corrcoef(pd.Series(v).rank(), pd.Series(t[sample]).rank())[0, 1]
        if r > 0.99:
            out.append(c)
    return out


def check_windows(df: pd.DataFrame, w: Windows) -> None:
    """The public check and the private test windows must hold enough payments to mean anything. A file whose newest
    weeks are sparse (or whose dates were misread) would otherwise build a model on nothing and crash the queue."""
    iso = w.iso()
    names = {"leaderboard": ("public check", iso["leaderboard_start"], iso["holdout_start"]),
             "holdout": ("private test", iso["holdout_start"], iso["holdout_end"])}
    counts = df["part"].value_counts()
    first, last = df["transaction_time"].min().strftime("%Y-%m-%d"), df["transaction_time"].max().strftime("%Y-%m-%d")
    for part, (label, a, b) in names.items():
        n = int(counts.get(part, 0))
        if n < MIN_WINDOW_ROWS:
            raise ValueError(
                f"The {label} days ({a} to {b}) hold only {n:,} payments; at least {MIN_WINDOW_ROWS:,} are needed. "
                f"Your file runs {first} to {last}. Check that the dates were read correctly, or upload a file with more recent payments."
            )


def apply_analyst_labels(df: pd.DataFrame, labels: dict[str, tuple[int, str]]) -> tuple[pd.DataFrame, int]:
    """labels: transaction_id -> (0 or 1, label_time). Returns the frame and how many rows changed."""
    if not labels:
        return df, 0
    out = df.copy()
    hit = out["transaction_id"].astype(str).isin(labels.keys())
    for i in out.index[hit]:
        lab, when = labels[str(out.at[i, "transaction_id"])]
        out.at[i, "is_fraud"] = int(lab)
        out.at[i, "label_time"] = pd.Timestamp(when) if lab == 1 else pd.NaT
    return out, int(hit.sum())


def _part(name: str, d: pd.DataFrame, y: pd.Series) -> SplitPart:
    pos = int(y.sum())
    p = SplitPart(name=name, rows=len(d), positives=pos, positive_rate=round(pos / len(d), 6) if len(d) else 0.0)  # type: ignore[arg-type]
    if len(d):
        p.time_min = str(d["transaction_time"].min())
        p.time_max = str(d["transaction_time"].max())
    return p


def protect_fraud(df: pd.DataFrame, settings: FraudSettings, as_of: str, salt: str, out_dir: Path, private_dir: Path, *,
                  simulated: bool, analyst_labels: dict[str, tuple[int, str]] | None = None, version: int = 2) -> tuple[ProtectReport, Transform, Windows]:
    out_dir.mkdir(parents=True, exist_ok=True)
    private_dir.mkdir(parents=True, exist_ok=True)
    w = windows(as_of, settings.label_delay_days)
    df = df[df["transaction_time"] < w.as_of_end].copy()
    if version >= 2:
        # a payment's exact second plus its amount can identify a customer who knows one of their own payments;
        # the minute is all a model needs
        df["transaction_time"] = df["transaction_time"].dt.floor("min")
    check_room(df, w)
    findings: list[Finding] = []

    df, n_analyst = apply_analyst_labels(df, analyst_labels or {})
    if n_analyst:
        findings.append(Finding(check="analyst_labels", severity="info", column=None, action="relabeled",
                                reason=f"{n_analyst} verdicts from your analysts replaced the file's labels, dated when they were given.",
                                evidence={"rows": n_analyst}))

    hashed_cols = []
    maps = []
    for c in HASHED:
        if c in df.columns:
            df[c], m = hash_ids(df[c], salt, keyed=version >= 2)
            m.insert(0, "field", c)
            maps.append(m)
            hashed_cols.append(c)
    if maps:
        secure_store.to_csv(pd.concat(maps), private_dir / "id_map.csv")  # the only way back to real IDs: encrypted
        findings.append(Finding(check="hashed_ids", severity="info", column=None, action="hashed",
                                reason="Customer and merchant IDs are scrambled with a key that stays on this machine. Solvers can still see "
                                       "that two payments share a customer, never who it is."
                                       + (" Payment times are rounded to the minute." if version >= 2 else ""),
                                evidence={"columns": hashed_cols, "keyed": version >= 2, "time_rounded": version >= 2}))

    df = label_parts(df, w)
    check_windows(df, w)
    features = [c for c in df.columns if c not in NOT_FEATURES]
    for c in clock_counters(df, features):
        findings.append(Finding(check="clock_counter", severity="medium", column=c, action="dropped",
                                reason=f"{c} counts time itself. A model would learn when a payment happened, not what makes it fraud, "
                                       "and recent payments look safe only because their fraud is not confirmed yet.",
                                evidence={"rank_corr_with_time": 1.0}))
    clocks = {f.column for f in findings if f.check == "clock_counter"}
    sample = df.sample(n=min(CHECK_SAMPLE, len(df)), random_state=42) if len(df) > CHECK_SAMPLE else df
    ctx = CheckContext(df=sample[features].assign(is_fraud=sample["is_fraud"].to_numpy()).reset_index(drop=True),
                       target="is_fraud", positive=1, time_column="transaction_time")
    ctx.dropped |= {"transaction_id"} | clocks  # the case key: kept for the queue, never a feature
    for check in COLUMN_CHECKS:
        check(ctx)
    dropped = {f.column for f in ctx.findings if f.action == "dropped"}
    ctx.findings = [f for f in ctx.findings if not (f.action in ("warned", "masked") and f.column in dropped)]
    ctx.masked -= dropped
    findings += ctx.findings
    kept = [c for c in features if c not in ctx.dropped]
    counts = summary_counts(df)
    findings.append(Finding(
        check="label_maturity", severity="info", column=None, action="relabeled",
        reason=(f"{counts['frauds_unconfirmed_in_train']:,} frauds were not yet confirmed at training time, so the model learns "
                f"them as unknown, as it would have then. A {w.delay_days}-day gap separates training from the test days."),
        evidence={"frauds_unconfirmed_in_train": counts["frauds_unconfirmed_in_train"], "embargo_days": w.delay_days},
    ))

    transform = Transform(target_column="is_fraud", positive_label=1, time_column="transaction_time", kept=kept,
                          dropped=sorted(ctx.dropped), masked=sorted(ctx.masked),
                          reasons={f.column: f.reason for f in findings if f.column})
    feats = transform.apply(df.drop(columns=["is_fraud"]))
    train_customers = set(df.loc[df["part"] == "train", "customer_id"]) if "customer_id" in df.columns else set()
    checksums: dict[str, str] = {}
    parts = []
    for name in ("train", "leaderboard", "holdout"):
        m = (df["part"] == name).to_numpy()
        f = feats.loc[m]
        y = df.loc[m, "y_train" if name == "train" else "y_eval"].rename("label").astype(int)
        fp, lp, mp = out_dir / f"{name}.csv", out_dir / f"{name}_labels.csv", out_dir / f"{name}_meta.csv"
        if name == "train":
            pd.concat([f, y], axis=1).to_csv(fp, index=False)  # solvers get labels for train only
        else:
            f.to_csv(fp, index=False)
        y.to_csv(lp, index=False)
        meta = pd.DataFrame({
            "day": df.loc[m, "transaction_time"].dt.strftime("%Y-%m-%d").to_numpy(),
            "amount": df.loc[m, "amount"].round(2).to_numpy(),
            "new_customer": (~df.loc[m, "customer_id"].isin(train_customers)).astype(int).to_numpy() if train_customers else 0,
        })
        meta.to_csv(mp, index=False)
        for p in (fp, lp, mp):
            checksums[p.name] = sha256_file(p)
        parts.append(_part(name, df.loc[m], y))
    recent = df.loc[df["part"] == "immature"]
    secure_store.to_csv(recent.drop(columns=["y_train", "y_eval", "part"]), private_dir / "recent.csv")
    transform.save(out_dir / "transform.json")

    current_tool = None
    if "current_score" in df.columns and "current_score" in kept:
        m = (df["part"] == "holdout").to_numpy()
        cs = pd.to_numeric(df.loc[m, "current_score"], errors="coerce").fillna(0.0).to_numpy(dtype=float)
        q = fraud_queue(df.loc[m, "y_eval"].to_numpy(), cs, df.loc[m, "amount"].to_numpy(dtype=float),
                        df.loc[m, "transaction_time"].dt.strftime("%Y-%m-%d").to_numpy(), settings.daily_capacity, settings.fraud_fee, settings.review_cost)
        current_tool = {"column": "current_score", "amount_per_day": round(q["amount_per_day"], 2), "precision": round(q["precision"], 4),
                        "false_alarms_per_1000": round(q["false_alarms_per_1000"], 2), "net_per_day": round(q["net_per_day"], 2)}
        findings.append(Finding(check="current_tool", severity="info", column="current_score", action="warned",
                                reason=f"Your current tool's score was kept as an input. Ranked the same way on the test days, it catches "
                                       f"${q['amount_per_day']:,.0f} of fraud per day in a {settings.daily_capacity}-case queue; every version is compared with that.",
                                evidence=current_tool))
    order = {"high": 0, "medium": 1, "info": 2}
    findings.sort(key=lambda f: order[f.severity])
    iso = w.iso()
    report = ProtectReport(
        strategy="time_embargo",
        parts=parts,
        findings=findings,
        kept_columns=kept,
        dropped_columns=sorted(c for c in ctx.dropped if c != "transaction_id"),
        masked_columns=sorted(ctx.masked),
        checksums=checksums,
        hashed_columns=hashed_cols,
        current_tool=current_tool,
        maturity=MaturitySummary(
            as_of=iso["as_of"], label_delay_days=w.delay_days, label_time_simulated=simulated, train_end=iso["train_end"],
            embargo_start=iso["embargo_start"], embargo_end=iso["embargo_end"], leaderboard_start=iso["leaderboard_start"],
            holdout_start=iso["holdout_start"], holdout_end=iso["holdout_end"], immature_start=iso["immature_start"],
            analyst_labels=n_analyst, **counts,
        ),
    )
    (out_dir / "leakage_report.json").write_text(json.dumps(report.model_dump(), indent=2, default=str))
    return report, transform, w


def new_customer_share(meta: pd.DataFrame) -> float:
    return float(np.mean(meta["new_customer"])) if len(meta) else 0.0
