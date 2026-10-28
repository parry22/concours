"""Acceptance on the real template data. Fraud: planted leak caught, no false positives. Churn: zero code changes."""
from pathlib import Path

from app.models import ProblemSpec
from app.packager.profile import profile_dataframe
from app.packager.protect import protect


def test_fraud_template(fraud_df, tmp_path: Path):
    spec = ProblemSpec(template="fraud", target_column="TX_FRAUD", positive_label=1, time_column="TX_DATETIME")
    report, transform = protect(fraud_df, spec, tmp_path)
    by_col = {f.column: f for f in report.findings}
    assert by_col["TX_FRAUD_SCENARIO"].severity == "high" and by_col["TX_FRAUD_SCENARIO"].action == "dropped"
    assert by_col["TRANSACTION_ID"].action == "dropped"
    for c in ("TX_AMOUNT", "CUSTOMER_ID", "TERMINAL_ID"):
        assert c not in by_col, f"false positive on {c}: {by_col.get(c)}"
    assert report.strategy == "time"
    assert [p.rows for p in report.parts] == [207849, 29693, 59386]
    assert all(t.name for t in report.parts)
    assert (tmp_path / "holdout_labels.csv").exists() and "holdout.csv" in report.checksums
    assert "TX_FRAUD_SCENARIO" not in transform.kept


def test_churn_template(churn_df, tmp_path: Path):
    spec = ProblemSpec(template="churn", target_column="Churn", positive_label=1, time_column=None)
    report, transform = protect(churn_df, spec, tmp_path)
    assert report.strategy == "stratified"
    by_col = {f.column: f for f in report.findings}
    assert by_col["Status"].action == "warned"  # strong but not a leak (AUC 0.80)
    assert report.rows_removed > 0  # the dataset ships 300 exact duplicates
    assert sum(p.rows for p in report.parts) == len(churn_df) - report.rows_removed
    assert "Churn" not in transform.kept


def test_profile_masks_and_finds_target(churn_df):
    p = profile_dataframe(churn_df)
    assert p.n_rows == 3150 and p.target_candidates[0] == "Churn"
    assert len(p.sample_rows) == 20 and len(p.preview_rows) == 10
    assert abs(p.positive_rate - 0.157) < 0.01
