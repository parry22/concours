"""Fraud focus: schema mapping, late labels and the embargo, the capacity metric, the five gates, protection,
the three questions, reasons and drift. Synthetic data, so these run without the sample download."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.fraud import gates
from app.fraud.intake import parse, turn
from app.fraud.labels import assign, known_label, label_parts, summary_counts, windows
from app.fraud.protect import hash_ids, protect_fraud
from app.fraud.reasons import describe, top_reasons
from app.fraud.schema import canonical, simulate_label_time, suggest, validate
from app.fraud.service import psi
from app.models import FraudSettings
from app.shared.metrics import compute, fraud_queue

ROOT = Path(__file__).resolve().parents[2]


def synthetic(days: int = 150, per_day: int = 300, seed: int = 0) -> pd.DataFrame:
    """Handbook-shaped raw data: big amounts are fraud, plus a scenario column that leaks the label."""
    rng = np.random.default_rng(seed)
    n = days * per_day
    t = pd.Timestamp("2018-04-01") + pd.to_timedelta(np.sort(rng.uniform(0, days * 86400, n)), unit="s")
    amount = np.round(rng.gamma(2.0, 30.0, n), 2)
    fraud = ((amount > 200) | (rng.random(n) < 0.004)).astype(int)
    return pd.DataFrame({
        "TRANSACTION_ID": np.arange(n) + 1000,
        "TX_DATETIME": t.strftime("%Y-%m-%d %H:%M:%S"),
        "CUSTOMER_ID": rng.integers(0, 800, n),
        "TERMINAL_ID": rng.integers(0, 1500, n),
        "TX_AMOUNT": amount,
        "TX_FRAUD": fraud,
        "TX_FRAUD_SCENARIO": fraud * rng.integers(1, 4, n),
    })


@pytest.fixture(scope="module")
def raw() -> pd.DataFrame:
    return synthetic()


@pytest.fixture(scope="module")
def canon(raw) -> pd.DataFrame:
    df, simulated = canonical(raw, {k: v for k, v in suggest(raw).items() if v})
    assert simulated
    return df


# ---------- schema ----------


def test_mapping_suggested_for_the_sample_names(raw):
    m = suggest(raw)
    assert m["transaction_id"] == "TRANSACTION_ID" and m["transaction_time"] == "TX_DATETIME"
    assert m["amount"] == "TX_AMOUNT" and m["customer_id"] == "CUSTOMER_ID" and m["is_fraud"] == "TX_FRAUD"
    assert m["merchant_or_terminal_id"] == "TERMINAL_ID" and m["label_time"] is None
    assert validate(raw, m) == []


def test_mapping_suggested_for_renamed_columns(raw):
    renamed = raw.rename(columns={"TRANSACTION_ID": "payment_id", "TX_DATETIME": "created_at", "TX_AMOUNT": "Amount (USD)",
                                  "CUSTOMER_ID": "user_id", "TX_FRAUD": "chargeback", "TERMINAL_ID": "store"})
    renamed["is_fraud"] = renamed["chargeback"].map({1: "yes", 0: "no"})
    renamed = renamed.drop(columns=["chargeback"])
    m = suggest(renamed)
    assert m == {"transaction_id": "payment_id", "transaction_time": "created_at", "amount": "Amount (USD)", "customer_id": "user_id",
                 "is_fraud": "is_fraud", "merchant_or_terminal_id": "store", "currency": None, "label_time": None}
    df, _ = canonical(renamed, {k: v for k, v in m.items() if v})
    assert set(df["is_fraud"].unique()) == {0, 1} and df["amount"].dtype == float
    assert {"transaction_id", "transaction_time", "amount", "customer_id", "is_fraud", "merchant_or_terminal_id", "label_time"} <= set(df.columns)


def test_mapping_problems_are_plain_words(raw):
    bad = dict(suggest(raw))
    bad["amount"] = None
    assert any("amount" in p for p in validate(raw, bad))
    bad = dict(suggest(raw))
    bad["transaction_time"] = "TX_AMOUNT"
    bad["amount"] = "TX_AMOUNT"
    assert any("one field only" in p for p in validate(raw, bad))


def test_label_time_simulated_seeded_and_only_for_fraud(canon):
    lt, t, y = canon["label_time"], canon["transaction_time"], canon["is_fraud"]
    assert lt[y == 0].isna().all() and lt[y == 1].notna().all()
    delay = (lt[y == 1] - t[y == 1]).dt.total_seconds() / 86400
    assert delay.min() >= 7 and delay.max() <= 60
    again = simulate_label_time(t, y)
    assert again.equals(simulate_label_time(t, y))


# ---------- windows, embargo, maturity ----------


def test_windows_order_and_embargo():
    w = windows("2018-08-31", 30, holdout_days=14, leaderboard_days=7)
    assert (w.immature_start - w.holdout_start).days == 14
    assert (w.holdout_start - w.leaderboard_start).days == 7
    assert (w.leaderboard_start - w.train_end).days == 30  # the embargo equals the label delay
    assert (w.as_of_end - w.immature_start).days == 30  # the newest 30 days have no mature labels
    t = pd.Series(pd.to_datetime(["2018-05-01", w.train_end.strftime("%Y-%m-%d"), w.leaderboard_start.strftime("%Y-%m-%d"),
                                  w.holdout_start.strftime("%Y-%m-%d"), "2018-08-31 23:00", "2018-09-01"], format="mixed"))
    assert list(assign(t, w)) == ["train", "embargo", "leaderboard", "holdout", "immature", "future"]


def test_label_known_only_after_confirmation():
    y = pd.Series([1, 1, 0])
    lt = pd.Series(pd.to_datetime(["2018-05-01", "2018-07-01", None]))
    assert list(known_label(y, lt, pd.Timestamp("2018-06-01"))) == [1, 0, 0]


def test_training_labels_are_as_known_at_the_cutoff(canon):
    w = windows(canon["transaction_time"].max(), 30)
    df = label_parts(canon, w)
    tr = df[df["part"] == "train"]
    late = tr[(tr["is_fraud"] == 1) & (tr["label_time"] >= w.train_end)]
    assert len(late) > 0 and (late["y_train"] == 0).all()  # confirmed after the cutoff: unknown to training
    early = tr[(tr["is_fraud"] == 1) & (tr["label_time"] < w.train_end)]
    assert (early["y_train"] == 1).all()
    c = summary_counts(df)
    assert c["frauds_unconfirmed_in_train"] == len(late) and c["embargo_rows"] == int((df["part"] == "embargo").sum())
    ev = df[df["part"].isin(["leaderboard", "holdout"])]
    assert (ev["y_eval"] <= ev["is_fraud"]).all()  # evaluation never invents a fraud, only misses unconfirmed ones


def test_nothing_from_the_embargo_is_written(canon, tmp_path):
    as_of = canon["transaction_time"].max().strftime("%Y-%m-%d")
    rep, _, w = protect_fraud(canon, FraudSettings(), as_of, "salt", tmp_path / "p", tmp_path / "x", simulated=True)
    for name in ("train", "leaderboard", "holdout"):
        meta = pd.read_csv(tmp_path / "p" / f"{name}_meta.csv")
        days = pd.to_datetime(meta["day"])
        assert not ((days >= w.train_end) & (days < w.leaderboard_start)).any()
    tr = pd.read_csv(tmp_path / "p" / "train.csv")
    assert pd.to_datetime(tr["transaction_time"]).max() < w.train_end
    ho = pd.read_csv(tmp_path / "p" / "holdout_meta.csv")
    assert pd.to_datetime(ho["day"]).max() < w.immature_start
    assert rep.maturity.frauds_unconfirmed_in_train > 0
    assert rep.maturity.embargo_rows > 0 and rep.strategy == "time_embargo"


def test_not_enough_history_is_explained(canon, tmp_path):
    with pytest.raises(ValueError, match="Not enough history"):
        protect_fraud(canon, FraudSettings(label_delay_days=90), canon["transaction_time"].max().strftime("%Y-%m-%d"), "s",
                      tmp_path / "p", tmp_path / "x", simulated=True)


# ---------- protection ----------


def test_ids_hashed_with_salt_and_mapping_kept_private(canon, tmp_path):
    as_of = canon["transaction_time"].max().strftime("%Y-%m-%d")
    rep, transform, _ = protect_fraud(canon, FraudSettings(), as_of, "salt-a", tmp_path / "p", tmp_path / "priv", simulated=True)
    tr = pd.read_csv(tmp_path / "p" / "train.csv")
    assert not set(tr["customer_id"]) & set(canon["customer_id"])  # no raw ID survives
    assert set(rep.hashed_columns) == {"customer_id", "merchant_or_terminal_id"}
    from app import secure_store  # noqa: PLC0415

    assert (tmp_path / "priv" / "id_map.csv").read_bytes().startswith(secure_store.MAGIC)  # encrypted at rest
    m = secure_store.read_csv(tmp_path / "priv" / "id_map.csv")
    assert set(m["field"]) == {"customer_id", "merchant_or_terminal_id"}
    assert not (tmp_path / "p" / "id_map.csv").exists()
    h1, _ = hash_ids(pd.Series([1, 2, 1]), "salt-a")
    h2, _ = hash_ids(pd.Series([1, 2, 1]), "salt-b")
    assert h1[0] == h1[2] and h1[0] != h2[0] and (h1 > 0).all()


def test_scenario_leak_caught_and_card_numbers_dropped(canon, tmp_path):
    df = canon.copy()
    luhn = ["4111111111111111", "4012888888881881", "5555555555554444", "378282246310005"]
    df["card_number"] = [luhn[i % 4] for i in range(len(df))]
    as_of = df["transaction_time"].max().strftime("%Y-%m-%d")
    rep, transform, _ = protect_fraud(df, FraudSettings(), as_of, "s", tmp_path / "p", tmp_path / "x", simulated=True)
    by = {f.column: f for f in rep.findings if f.column}
    assert by["TX_FRAUD_SCENARIO"].check == "target_leak" and by["TX_FRAUD_SCENARIO"].action == "dropped"
    assert by["card_number"].check == "pii" and by["card_number"].action == "dropped"
    assert "card_number" not in transform.kept and "TX_FRAUD_SCENARIO" not in transform.kept
    assert "transaction_id" not in transform.kept  # the case key is never a feature


def test_future_information_caught(canon, tmp_path):
    df = canon.copy()
    total = df.groupby("customer_id")["is_fraud"].transform("sum")  # computed over the whole file: knows the future
    df["customer_total_frauds"] = total
    df["chargeback_date"] = (df["transaction_time"] + pd.Timedelta(days=20)).dt.strftime("%Y-%m-%d")
    df["customer_segment"] = df["customer_id"] % 5  # constant per customer but unrelated to fraud: kept
    as_of = df["transaction_time"].max().strftime("%Y-%m-%d")
    rep, transform, _ = protect_fraud(df, FraudSettings(), as_of, "s", tmp_path / "p", tmp_path / "x", simulated=True)
    fut = {f.column for f in rep.findings if f.check == "future_info"}
    assert {"customer_total_frauds", "chargeback_date"} <= fut
    assert "customer_segment" in transform.kept


def test_analyst_labels_override_with_label_time(canon, tmp_path):
    as_of = canon["transaction_time"].max().strftime("%Y-%m-%d")
    w = windows(as_of, 30)
    legit = canon[(canon["is_fraud"] == 0) & (canon["transaction_time"] < w.train_end - pd.Timedelta(days=40))].iloc[0]
    labels = {str(legit["transaction_id"]): (1, (w.train_end - pd.Timedelta(days=5)).strftime("%Y-%m-%d"))}
    rep, _, _ = protect_fraud(canon, FraudSettings(), as_of, "s", tmp_path / "p", tmp_path / "x", simulated=True, analyst_labels=labels)
    assert rep.maturity.analyst_labels == 1


# ---------- the capacity metric ----------


def test_queue_metric_by_day_and_capacity():
    y = np.array([1, 0, 1, 0, 1, 0])
    s = np.array([0.9, 0.8, 0.1, 0.7, 0.6, 0.2])
    a = np.array([100, 10, 50, 5, 30, 1.0])
    d = np.array(["a", "a", "a", "b", "b", "b"])
    q = fraud_queue(y, s, a, d, capacity=1, review_cost=2)
    assert list(q["caught_amount_by_day"]) == [100, 30]  # day b: 0.6 x 30 = 18 beats 0.7 x 5 = 3.5
    assert q["amount_per_day"] == 65 and q["net_per_day"] == 63 and q["precision"] == 1.0
    assert q["count_per_day"] == 1.0 and q["false_alarms_per_1000"] == 0.0
    assert compute("fraud_amount_per_day", y, s, {"capacity": 1}, {"amount": a, "day": d}) == 65


def test_fee_lifts_small_frauds_into_the_queue():
    y = np.array([1, 0])
    s = np.array([0.9, 0.2])
    a = np.array([5.0, 100.0])
    d = np.array(["x", "x"])
    assert fraud_queue(y, s, a, d, capacity=1, fee=0)["caught_count_by_day"][0] == 0  # 4.5 < 20
    assert fraud_queue(y, s, a, d, capacity=1, fee=25)["caught_count_by_day"][0] == 1  # 27 > 25


def test_false_alarms_per_thousand():
    y = np.array([0, 0, 0, 0, 1])
    s = np.array([0.9, 0.1, 0.1, 0.1, 0.8])
    q = fraud_queue(y, s, np.ones(5), np.zeros(5), capacity=2)
    assert q["false_alarms_per_1000"] == 250.0 and q["precision"] == 0.5


# ---------- the five gates ----------


def test_gate_hidden_data():
    assert gates.hidden_data("holdout", 1.0).passed
    assert not gates.hidden_data("leaderboard", 1.0).passed
    assert not gates.hidden_data("holdout", None).passed


def test_gate_same_rows():
    a = np.zeros(10)
    assert gates.same_rows(a, a, 10, 2, 1).passed
    assert not gates.same_rows(a, None, 10, 2, 1).passed
    assert not gates.same_rows(a, np.zeros(9), 10, 2, 1).passed


def test_gate_luck_clear_winner_passes():
    rng = np.random.default_rng(1)
    champ = rng.uniform(900, 1100, 14)
    g = gates.luck(champ + 150, champ)
    assert g.passed and g.detail["win_share"] == 1.0 and g.line == "Wins in 100% of resamples"


def test_gate_luck_wins_on_average_but_fails():
    """Better on average, but the whole gain comes from one lucky day: most resamples without that day lose."""
    champ = np.full(14, 1000.0)
    chal = np.full(14, 990.0)
    chal[3] = 1600.0  # one big day
    assert chal.mean() > champ.mean()
    g = gates.luck(chal, champ)
    assert not g.passed and g.detail["win_share"] < 0.95
    assert "needs 95%" in g.line


def test_gate_luck_is_seeded():
    rng = np.random.default_rng(2)
    a, b = rng.uniform(0, 10, 14), rng.uniform(0, 10, 14)
    assert gates.luck(a, b).detail == gates.luck(a, b).detail


def test_gate_segments_catch_a_hidden_regression():
    y = np.array([1, 1, 1, 1])
    amount = np.array([20.0, 100.0, 600.0, 30.0])
    new = np.array([0, 0, 0, 1])
    champ = np.array([True, True, True, True])
    chal = np.array([False, True, True, True])  # loses the under-50 fraud of a returning customer
    g = gates.segments(y, amount, new, chal, champ)
    assert not g.passed and "Payments under 50" in g.line
    ok = gates.segments(y, amount, new, champ, champ)
    assert ok.passed and ok.line == "No segment drops more than 5%"
    names = {r["segment"] for r in ok.detail["segments"]}
    assert names == {"Payments under 50", "Payments 50 to 500", "Payments over 500", "New customers", "Returning customers"}


def test_gate_speed():
    assert gates.speed(1.2).passed and gates.speed(1.2).line == "Scores 10,000 payments in 1.2 s"
    assert not gates.speed(6.0).passed and not gates.speed(None).passed


def test_evaluate_runs_all_five_in_order():
    rng = np.random.default_rng(3)
    n = 14 * 50
    day = np.repeat(np.arange(14), 50).astype(str)
    y = (rng.random(n) < 0.1).astype(int)
    amount = rng.uniform(5, 800, n)
    champ = rng.random(n)
    chal = np.where(y == 1, champ + 0.5, champ)  # strictly better at ranking frauds
    out = gates.evaluate(chal, champ, y, amount, day, rng.integers(0, 2, n), FraudSettings(daily_capacity=10),
                         champion_version=1, private_score=1.0, seconds_per_10k=0.5)
    assert [g.key for g in out] == ["hidden_data", "same_rows", "luck", "segments", "speed"]
    assert gates.all_passed(out)
    worse = gates.evaluate(champ, chal, y, amount, day, rng.integers(0, 2, n), FraudSettings(daily_capacity=10),
                           champion_version=1, private_score=1.0, seconds_per_10k=0.5)
    assert not gates.all_passed(worse)
    unpaired = gates.evaluate(chal, None, y, amount, day, np.zeros(n), FraudSettings(), champion_version=1, private_score=1.0, seconds_per_10k=0.5)
    assert not unpaired[1].passed and not gates.all_passed(unpaired)


# ---------- intake ----------


def test_three_questions_with_defaults():
    st = FraudSettings()
    st, _ = parse(0, "we can do about 150 a day", st)
    assert st.daily_capacity == 150
    st, _ = parse(1, "12 per review and a 25 chargeback fee", st)
    assert (st.review_cost, st.fraud_fee) == (12, 25)
    st, _ = parse(1, "about 8, no extra fee", st)
    assert (st.review_cost, st.fraud_fee) == (8, 0)
    st, _ = parse(2, "around 6 weeks", st)
    assert st.label_delay_days == 42
    st, _ = parse(0, "not sure", FraudSettings())
    assert st.daily_capacity == 200
    st, _ = parse(2, "", FraudSettings())
    assert st.label_delay_days == 30


def test_intake_finishes_after_three_answers():
    hist, st, done = [], FraudSettings(), False
    for a in ("200 cases a day", "10 per review, no fee", "30 days"):
        hist, st, msg, done = turn(hist, a, st)
    assert done and sum(m.role == "user" for m in hist) == 3 and hist[0].role == "assistant"


# ---------- reasons ----------


def test_reasons_are_plain_english():
    assert describe("merchant_or_terminal_id_w_rate") == "Terminal had recent fraud"
    assert describe("customer_id_amt_ratio") == "Unusual amount for this customer"
    assert describe("amount") == "Unusual amount"
    assert describe("v_cust_tested_72h") == "Card was tested in the last 3 days"
    contrib = np.array([[0.5, -1.0, 0.3, 0.3], [0.0, 0.0, 0.0, 0.0]])
    out = top_reasons(contrib, ["amount", "_hour", "merchant_or_terminal_id_w_rate", "merchant_or_terminal_id_w_pos"])
    assert out[0][0][0] == "Terminal had recent fraud" and out[0][1][0] == "Unusual amount"  # merged 0.6, then 0.5
    assert len(out[0]) == 2 and out[1] == []
    for text, _ in out[0]:
        assert not any(w in text.lower() for w in ("lightgbm", "logistic", "xgboost", "_"))


# ---------- drift ----------


def test_psi_flags_a_shift_only():
    rng = np.random.default_rng(4)
    base = rng.gamma(2, 30, 20000)
    assert psi(base, rng.gamma(2, 30, 5000)) < 0.05
    assert psi(base, np.r_[rng.gamma(2, 30, 3000), rng.uniform(0.5, 9.99, 2000)]) > 0.2


def test_inject_drift_adds_card_testing_then_cashouts(raw):
    sys.path.insert(0, str(ROOT / "scripts"))
    from inject_drift import CASHOUT_SCENARIO, TEST_SCENARIO, inject  # noqa: PLC0415

    out = inject(raw, start_day=100, terminals=10, bursts_per_day=2)
    new = out[out["TX_FRAUD_SCENARIO"].isin([TEST_SCENARIO, CASHOUT_SCENARIO])]
    tests, cash = new[new["TX_FRAUD_SCENARIO"] == TEST_SCENARIO], new[new["TX_FRAUD_SCENARIO"] == CASHOUT_SCENARIO]
    assert len(tests) > 0 and len(cash) > 0 and (new["TX_FRAUD"] == 1).all()
    assert (tests["TX_AMOUNT"] < 10).all() and tests["TERMINAL_ID"].nunique() <= 10
    assert (cash["TX_AMOUNT"] <= 140).all()  # sized like normal spending, under what the amount ranking flags
    first = pd.to_datetime(raw["TX_DATETIME"]).min().normalize()
    assert pd.to_datetime(new["TX_DATETIME"]).min() >= first + pd.Timedelta(days=100)
    assert out["TRANSACTION_ID"].is_unique
    again = inject(raw, start_day=100, terminals=10, bursts_per_day=2)
    assert again.equals(out)
