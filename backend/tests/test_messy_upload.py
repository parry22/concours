"""A real-world CSV: renamed columns, mixed date formats, currency symbols, blanks. The upload must read it or say why."""
import numpy as np
import pandas as pd
import pytest

from app.fraud.labels import windows, label_parts
from app.fraud.protect import check_windows
from app.fraud.schema import canonical, inspect_mapping, parse_amount, parse_time, suggest


def test_amounts_with_symbols_and_separators():
    s = pd.Series(["$1,234.50", "€87.38", "12.30", "1.234,50", "", " 5 ", "abc"])
    out = parse_amount(s)
    assert out.tolist()[:4] == [1234.5, 87.38, 12.3, 1234.5]
    assert np.isnan(out[4]) and out[5] == 5.0 and np.isnan(out[6])


def test_mixed_date_formats_are_read_and_iso_is_never_day_first():
    s = pd.Series(["2018-04-12 13:05:00", "2018-04-12T13:05:00Z", "12/04/2018 13:05", "not a date", ""])
    t, notes = parse_time(s)
    assert t[0] == pd.Timestamp("2018-04-12 13:05") and t[1] == pd.Timestamp("2018-04-12 13:05")
    assert t[2].month == 4 and t[2].day == 12  # day first, because another row would otherwise need a month of 13
    assert pd.isna(t[3]) and pd.isna(t[4])
    assert any("date formats" in n for n in notes)


def test_suggest_handles_common_renames():
    df = pd.DataFrame({"txn_ref": ["a"], "posted_at": ["2018-04-01 00:00:00"], "cust": [1], "store": [2], "amt": ["$1"], "fraud_flag": ["no"]})
    sug = suggest(df)
    assert sug["transaction_id"] == "txn_ref" and sug["transaction_time"] == "posted_at" and sug["customer_id"] == "cust"
    assert sug["amount"] == "amt" and sug["is_fraud"] == "fraud_flag" and sug["merchant_or_terminal_id"] == "store"


def test_inspect_mapping_reports_examples_and_left_out_rows():
    n = 400
    df = pd.DataFrame({"txn_ref": [f"T{i}" for i in range(n)], "posted_at": pd.date_range("2018-01-01", periods=n, freq="h").strftime("%d/%m/%Y %H:%M"),
                       "cust": np.arange(n) % 7, "amt": ["$%d.50" % i for i in range(n)], "fraud_flag": ["yes" if i % 50 == 0 else "no" for i in range(n)]})
    df.loc[:9, "amt"] = ""
    m = {"transaction_id": "txn_ref", "transaction_time": "posted_at", "amount": "amt", "customer_id": "cust", "is_fraud": "fraud_flag"}
    problems, notes, rng = inspect_mapping(df, m)
    assert problems == []
    assert any("10 payments without an amount" in x for x in notes)
    assert rng["days"] == 17 and rng["start"] == "2018-01-01"
    df["amt"] = "n/a"
    problems, _, _ = inspect_mapping(df, m)
    assert any("More than 20%" in x for x in problems)
    df["amt"] = "abc"
    problems, _, _ = inspect_mapping(df, m)
    assert any("does not read as numbers. Examples: abc" in x for x in problems)
    out, simulated = canonical(df.assign(amt="1.00"), m)
    assert len(out) == n and simulated


def test_sparse_newest_weeks_are_refused_with_a_sentence():
    t = pd.date_range("2018-01-01", "2018-04-30", freq="30min")
    df = pd.DataFrame({"transaction_time": t, "amount": 1.0, "is_fraud": 0, "label_time": pd.NaT})
    df = df[(df["transaction_time"] < "2018-03-15") | (df["transaction_time"] > "2018-04-29")]  # a gap where the windows fall
    w = windows("2018-04-30", 14)
    with pytest.raises(ValueError, match="hold only"):
        check_windows(label_parts(df, w), w)
