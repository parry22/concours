"""Build a ValueReport for a scored submission. Fast path for the leaderboard, full path for the value endpoint."""
from __future__ import annotations

from app.models import DataProfile, ProblemSpec, ProtectReport, SubmissionRow, ValueParam, ValueReport
from app.value import model, params as P, scores as S

BASELINE_SOLVER = "baseline_logreg"


def eval_split(finalized: bool) -> str:
    return "holdout" if finalized else "leaderboard"


def _money(x: float) -> str:
    sign = "-" if x < 0 else ""
    return f"{sign}${abs(x):,.0f}"


def build_report(
    project_id: str,
    spec: ProblemSpec,
    sub: SubmissionRow,
    sc: dict,
    prm: list[ValueParam],
    *,
    finalized: bool,
    baseline: SubmissionRow | None = None,
    baseline_scores: dict | None = None,
) -> ValueReport:
    split = eval_split(finalized)
    y_eval, s_eval = S.labels(project_id, split), sc[split]
    y_thr, s_thr = S.labels(project_id, "leaderboard"), sc["leaderboard"]
    e = model.Econ.from_params(prm)
    d = P.as_dict(prm)
    labels = {p.key: p.label for p in prm}

    thr = model.contract_threshold(spec, y_thr, s_thr)
    contract = model.point("contract", y_eval, s_eval, thr, e)
    pts, best_thr = model.curve(y_eval, s_eval, e)
    optimal = model.point("optimal", y_eval, s_eval, best_thr, e)

    base_pt = None
    if baseline is not None and baseline_scores is not None and baseline.id != sub.id:
        b_thr = model.contract_threshold(spec, y_thr, baseline_scores["leaderboard"])
        base_pt = model.point("baseline", y_eval, baseline_scores[split], b_thr, e)

    positives_per_month = d["rows_per_month"] * d["positive_rate"]
    exposure = positives_per_month * d["value_per_positive"]
    uplift = contract.net - base_pt.net if base_pt else None

    template = P._template(spec)
    assumptions = [f"{p.label}: {p.note}" if p.note else f"{p.label} is a placeholder." for p in prm if p.source == "default"]
    if finalized:
        assumptions.append("Threshold chosen on the public leaderboard slice, priced on the private holdout.")
    else:
        assumptions.append("Priced on the public leaderboard slice with a threshold chosen on that same slice. Finalize for the holdout figure.")
    if template == "fraud":
        assumptions.append("A stopped fraud saves its full amount. Chargeback fees and investigation time are not counted.")
    elif template == "churn":
        assumptions.append("Revenue kept is counted once per saved customer, not over their lifetime.")

    rng = f" (90% range {_money(contract.net_low)} to {_money(contract.net_high)})" if contract.net_low is not None and contract.net_high is not None else ""
    headline = f"Net value per month: {_money(contract.net)}{rng}"
    formula = (
        f"{contract.tp:,.0f} caught x {d['action_success_rate']:.0%} acted on x {_money(d['value_per_positive'])} each"
        f" - {contract.tp + contract.fp:,.0f} flagged x {_money(d['cost_per_action'])} to handle"
        f" - {contract.fp:,.0f} wrong flags x {_money(d['cost_per_false_positive'])} each"
        f", at {d['rows_per_month']:,.0f} rows per month"
    )
    return ValueReport(
        project_id=project_id,
        solver=sub.solver,
        baseline_solver=baseline.solver if base_pt else None,
        eval_split=split,  # type: ignore[arg-type]
        rows_eval=int(len(y_eval)),
        params=prm,
        contract=contract,
        optimal=optimal,
        baseline=base_pt,
        exposure_per_month=exposure,
        uplift_net=uplift,
        annual_net=contract.net * 12,
        curve=pts,
        sensitivity=model.sensitivity(contract.tp, contract.fp, e, labels),
        breakeven=model.breakeven(contract.tp, contract.fp, e),
        assumptions=assumptions,
        headline=headline,
        formula=formula,
    )


def report_for(
    project_id: str,
    spec: ProblemSpec,
    subs: list[SubmissionRow],
    solver: str | None,
    *,
    finalized: bool,
    profile: DataProfile | None,
    protect: ProtectReport | None,
    allow_refit: bool,
) -> ValueReport | None:
    """Report for `solver` (or the leader when None). None when nothing is scored or scores are unavailable."""
    from app.arena.leaderboard import rank  # noqa: PLC0415 - avoid an import cycle

    scored = [s for s in subs if s.status == "scored"]
    if not scored:
        return None
    if solver:
        sub = next((s for s in sorted(scored, key=lambda r: r.created_at, reverse=True) if s.solver == solver), None)
    else:
        leader = next((o for o in rank(subs, finalized) if o.is_leader), None)
        sub = next((s for s in scored if leader and s.id == leader.id), None)
    if sub is None:
        return None
    sc = S.split_scores(project_id, sub, spec, allow_refit=allow_refit)
    if sc is None:
        return None
    prm = P.resolve(project_id, spec, profile, protect)
    base = next((s for s in sorted(scored, key=lambda r: r.created_at, reverse=True) if s.solver == BASELINE_SOLVER), None)
    base_sc = S.split_scores(project_id, base, spec, allow_refit=allow_refit) if base is not None and base.id != sub.id else None
    return build_report(project_id, spec, sub, sc, prm, finalized=finalized, baseline=base if base_sc else None, baseline_scores=base_sc)


def summary_lines(rep: ValueReport | None) -> tuple[str | None, str | None]:
    """(savings_line, savings_formula) for the leaderboard card."""
    if rep is None:
        return None, None
    if rep.uplift_net is not None:
        line = f"Net value vs the baseline: {'+' if rep.uplift_net >= 0 else ''}{_money(rep.uplift_net)} per month"
    else:
        line = rep.headline.split(" (")[0]
    return line, rep.formula
