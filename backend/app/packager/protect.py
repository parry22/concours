"""Run the packager: checks, transform, split, write protected artifacts, report."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from app.models import Finding, ProblemSpec, ProtectReport
from app.packager.checks import (
    constant, cross_split_dup, id_like, pii, post_outcome_name, repeated_entity, sensitive, target_leak, temporal,
)
from app.packager.checks.base import CheckContext
from app.packager.fairness import sensitive_path
from app.packager.split import make_split, split_parts
from app.packager.transform import Transform
from app.templates import known_leaks, words

# sensitive and repeated_entity run first so a trait or an entity key is reported as such, not as an identifier;
# target_leak runs before constant: a rare-but-perfect column (99% zeros) is a leak, not noise
COLUMN_CHECKS = (sensitive.run, id_like.run, pii.run, post_outcome_name.run, target_leak.run, constant.run)


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def coerce_positive(df: pd.DataFrame, target: str, positive):
    """Match the positive label's type to the column dtype (e.g. "1" -> 1)."""
    s = df[target]
    if positive is None:
        vals = s.dropna().value_counts()
        return vals.index[-1] if len(vals) else None  # rarer value
    if pd.api.types.is_numeric_dtype(s):
        try:
            return type(s.dropna().iloc[0])(positive) if len(s.dropna()) else positive
        except (ValueError, TypeError):
            return positive
    return str(positive)


def run_column_checks(df: pd.DataFrame, spec: ProblemSpec) -> CheckContext:
    positive = coerce_positive(df, spec.target_column, spec.positive_label)
    ctx = CheckContext(df=df, target=spec.target_column, positive=positive, time_column=spec.time_column)
    # columns the template documents as recorded after the outcome but too weak for the statistical test alone
    for col, reason in known_leaks(spec.template).items():
        if col in df.columns and col != spec.target_column:
            ctx.drop(Finding(check="known_leak", severity="high", column=col, reason=reason, action="dropped", evidence={"source": "template"}))
    repeated_entity.run(ctx, words(spec.template, spec.business_template))
    for check in COLUMN_CHECKS:
        check(ctx)
    # a warned post-outcome column that was then dropped by target_leak: keep only the drop finding
    dropped = {f.column for f in ctx.findings if f.action == "dropped"}
    ctx.findings = [f for f in ctx.findings if not (f.action in ("warned", "masked") and f.column in dropped)]
    ctx.masked -= dropped
    return ctx


def protect(df: pd.DataFrame, spec: ProblemSpec, out_dir: Path) -> tuple[ProtectReport, Transform]:
    out_dir.mkdir(parents=True, exist_ok=True)
    ctx = run_column_checks(df, spec)
    findings: list[Finding] = list(ctx.findings)
    kept = [c for c in df.columns if c != spec.target_column and c not in ctx.dropped]
    transform = Transform(
        target_column=spec.target_column,
        positive_label=ctx.positive if not hasattr(ctx.positive, "item") else ctx.positive.item(),
        time_column=spec.time_column,
        kept=kept,
        dropped=sorted(ctx.dropped),
        masked=sorted(ctx.masked),
        reasons={f.column: f.reason for f in findings if f.column},
    )
    work = transform.apply(df, require_target=True)
    # set-aside columns ride along through the split, then leave before anything is written for solvers
    aside = list(ctx.set_aside_cols) + sorted(ctx.keep_aside - set(ctx.set_aside_cols))
    for c in aside:
        work[c] = df.loc[work.index, c]
    split = make_split(work, spec.target_column, spec.time_column, ctx.group_column, ctx.positive)
    split = temporal.run(split, spec.time_column, findings)
    features = [c for c in kept if c != spec.time_column] or kept
    removed = cross_split_dup.run(split, features, findings)
    sensitive_parts = {}
    for name in ("train", "leaderboard", "holdout"):
        part = getattr(split, name)
        sensitive_parts[name] = part[list(ctx.set_aside_cols)].copy()
        setattr(split, name, part.drop(columns=aside))

    # severity order: high first
    order = {"high": 0, "medium": 1, "info": 2}
    findings.sort(key=lambda f: order[f.severity])

    checksums: dict[str, str] = {}
    for name, part in (("train", split.train), ("leaderboard", split.leaderboard), ("holdout", split.holdout)):
        feats = part.drop(columns=[spec.target_column])
        labels = (part[spec.target_column] == ctx.positive).astype(int).rename("label")
        fp, lp = out_dir / f"{name}.csv", out_dir / f"{name}_labels.csv"
        if name == "train":
            pd.concat([feats, labels], axis=1).to_csv(fp, index=False)  # solvers get labels for train only
        else:
            feats.to_csv(fp, index=False)
        labels.to_csv(lp, index=False)
        checksums[fp.name] = sha256_file(fp)
        checksums[lp.name] = sha256_file(lp)
    for name, side in sensitive_parts.items():
        p = sensitive_path(out_dir, name)
        if ctx.set_aside_cols:
            side.to_csv(p, index=False)  # never staged for player or referee
        elif p.exists():
            p.unlink()
    transform.save(out_dir / "transform.json")
    report = ProtectReport(
        strategy=split.strategy,  # type: ignore[arg-type]
        parts=split_parts(split, spec.target_column, ctx.positive, spec.time_column),
        findings=findings,
        kept_columns=kept,
        dropped_columns=sorted(ctx.dropped),
        masked_columns=sorted(ctx.masked),
        rows_removed=removed,
        checksums=checksums,
        set_aside_columns=list(ctx.set_aside_cols),
        group_column=ctx.group_column if split.strategy == "group" else None,
    )
    (out_dir / "leakage_report.json").write_text(json.dumps(report.model_dump(), indent=2, default=str))
    return report, transform
