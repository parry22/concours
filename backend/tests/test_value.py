"""Value model: hand-computed money, operating points, bootstrap range, parameter sources."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app import config
from app.models import ProblemSpec, ProtectReport, SplitPart, ValueParam
from app.value import model as M
from app.value import params as P

# 10 rows: 2 positives (scores 0.9, 0.7), 8 negatives
Y = np.array([0, 0, 0, 0, 0, 0, 0, 0, 1, 1])
S = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.95, 0.8, 0.9, 0.7])
E = M.Econ(rows_per_month=1000, value_per_positive=100, action_success_rate=0.5, cost_per_action=2, cost_per_false_positive=10)


def test_counts_and_money_by_hand():
    # threshold 0.8 flags 0.95, 0.8, 0.9: one positive, two negatives
    assert M.counts(Y, S, 0.8) == (1, 2, 1, 6)
    scale = 1000 / 10
    gross, costs, net = M.money(1 * scale, 2 * scale, E)
    assert gross == 100 * 0.5 * 100  # 100 caught x 50% x $100
    assert costs == 300 * 2 + 200 * 10  # 300 flagged x $2 + 200 wrong x $10
    assert net == gross - costs
    pt = M.point("contract", Y, S, 0.8, E)
    assert (pt.tp, pt.fp, pt.fn, pt.tn) == (100, 200, 100, 600)
    assert pt.net == net and pt.recall == 0.5 and pt.fpr == 0.25 and pt.precision == pytest.approx(1 / 3)


def test_bootstrap_range_brackets_the_point():
    pt = M.point("contract", Y, S, 0.8, E)
    assert pt.net_low is not None and pt.net_high is not None
    assert pt.net_low <= pt.net <= pt.net_high
    assert pt.recall_low <= pt.recall <= pt.recall_high
    # deterministic
    again = M.point("contract", Y, S, 0.8, E)
    assert (again.net_low, again.net_high) == (pt.net_low, pt.net_high)


def test_curve_optimum_is_the_best_net():
    pts, thr = M.curve(Y, S, E)
    assert pts and thr in set(S)
    best = max(pts, key=lambda p: p.net)
    assert M.point("optimal", Y, S, thr, E).net == pytest.approx(best.net)
    # flagged share grows along the curve
    shares = [p.flagged_share for p in pts]
    assert shares == sorted(shares)


def test_contract_threshold_follows_the_metric():
    fpr_spec = ProblemSpec(target_column="y", primary_metric="recall_at_fpr", metric_params={"fpr": 0.125})
    thr = M.contract_threshold(fpr_spec, Y, S)
    assert M.counts(Y, S, thr)[1] == 1  # one negative allowed above the line
    k_spec = ProblemSpec(target_column="y", primary_metric="recall_at_top_k", metric_params={"top_k": 0.3})
    thr = M.contract_threshold(k_spec, Y, S)
    assert int((S >= thr).sum()) == 3


def test_sensitivity_and_breakeven():
    labels = {k: k for k in ("value_per_positive", "action_success_rate", "cost_per_action", "cost_per_false_positive", "rows_per_month")}
    sens = M.sensitivity(100, 200, E, labels)
    by = {s.key: s for s in sens}
    assert by["value_per_positive"].high_net > by["value_per_positive"].low_net
    assert by["cost_per_false_positive"].high_net < by["cost_per_false_positive"].low_net
    assert by["action_success_rate"].high_value <= 1.0
    be = M.breakeven(100, 200, E)
    # net = 100*0.5*100 - 300*2 - 200*c = 0  ->  c = 4400/200 = 22
    assert be["cost_per_false_positive"] == pytest.approx(22)
    # asr: 300*2 + 200*10 = asr*100*100 -> 0.26
    assert be["action_success_rate"] == pytest.approx(0.26)


def test_normalize_economics_aliases_and_junk():
    econ = {"monthly_volume": "5000", "cost_fn": 12, "cost_fp": None, "positive_rate": 0.1, "action_success_rate": -1, "nonsense": 3}
    assert P.normalize_economics(econ) == {"rows_per_month": 5000.0, "value_per_positive": 12.0}


def test_resolve_sources(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "WORKSPACE_DIR", tmp_path)
    pid = "p1"
    protected = tmp_path / pid / "protected"
    protected.mkdir(parents=True)
    rng = np.random.default_rng(0)
    y = (rng.random(400) < 0.1).astype(int)
    pd.DataFrame({"TX_AMOUNT": np.where(y == 1, 200.0, rng.uniform(10, 90, 400)), "other": 1, "label": y}).to_csv(protected / "train.csv", index=False)
    report = ProtectReport(
        strategy="time",
        parts=[
            SplitPart(name="train", rows=400, positives=int(y.sum()), positive_rate=float(y.mean()), time_min="2024-01-01", time_max="2024-02-15"),
            SplitPart(name="leaderboard", rows=100, positives=10, positive_rate=0.1, time_min="2024-02-15", time_max="2024-02-29"),
            SplitPart(name="holdout", rows=100, positives=10, positive_rate=0.1, time_min="2024-03-01", time_max="2024-03-31"),
        ],
        findings=[], kept_columns=[], dropped_columns=[], masked_columns=[],
    )
    spec = ProblemSpec(template="fraud", business_template="fraud", target_column="TX_FRAUD", economics={"cost_fp": 7})
    prm = {p.key: p for p in P.resolve(pid, spec, None, report)}
    assert prm["rows_per_month"].source == "data" and 190 < prm["rows_per_month"].value < 210  # 600 rows over about 3 months
    assert prm["positive_rate"].source == "data" and prm["positive_rate"].value == pytest.approx((y.sum() + 20) / 600)
    assert prm["value_per_positive"].source == "data" and prm["value_per_positive"].value == 200.0
    assert prm["cost_per_false_positive"].source == "user" and prm["cost_per_false_positive"].value == 7
    assert prm["action_success_rate"].source == "default" and prm["action_success_rate"].note
    # second call hits the derived cache
    assert P.resolve(pid, spec, None, report) == list(prm.values())


def test_params_hash_changes_with_values():
    a = [ValueParam(key="rows_per_month", label="x", value=1, source="user", unit="count")]
    b = [ValueParam(key="rows_per_month", label="x", value=2, source="user", unit="count")]
    assert P.params_hash(a) != P.params_hash(b)
