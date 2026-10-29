import numpy as np

from app.shared.metrics import compute, fraud_lift_in_capacity


def _data():
    rng = np.random.default_rng(3)
    n = 3000
    y = (rng.random(n) < 0.05).astype(int)
    amount = rng.gamma(2.0, 40.0, n)
    day = np.repeat(np.arange(10), n // 10)
    return y, amount, day


def test_constant_scores_zero_and_oracle_scores_one():
    y, amount, day = _data()
    assert fraud_lift_in_capacity(y, np.full(len(y), 0.5), amount, day, capacity=50)["lift"] == 0.0
    assert abs(fraud_lift_in_capacity(y, y.astype(float), amount, day, capacity=50)["lift"] - 1.0) < 1e-9
    assert fraud_lift_in_capacity(y, amount, amount, day, capacity=50)["lift"] == 0.0  # ranking by amount is the rule


def test_a_real_signal_lands_between_and_a_bad_one_below():
    y, amount, day = _data()
    rng = np.random.default_rng(4)
    good = y * 0.6 + rng.random(len(y)) * 0.5
    out = fraud_lift_in_capacity(y, good, amount, day, capacity=50)
    assert 0.0 < out["lift"] < 1.0
    assert out["rule_per_day"] <= out["model_per_day"] <= out["oracle_per_day"]
    bad = -amount  # smallest payments first: worse than the rule
    assert fraud_lift_in_capacity(y, bad, amount, day, capacity=50)["lift"] < 0.0


def test_compute_dispatch_needs_meta():
    y, amount, day = _data()
    v = compute("fraud_lift_in_capacity", y, y.astype(float), {"capacity": 50}, {"amount": amount, "day": day})
    assert abs(v - 1.0) < 1e-9
