"""Acceptance on the real template data. Fraud: planted leak caught, no false positives. Churn: zero code changes."""
from pathlib import Path

from app.models import ProblemSpec
from app.packager.profile import profile_dataframe
from app.packager.protect import protect
from app.templates import list_templates


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


def test_leads_template(leads_df, tmp_path: Path):
    spec = ProblemSpec(template="leads", target_column="y", positive_label="yes", time_column=None)
    report, transform = protect(leads_df, spec, tmp_path)
    by_col = {f.column: f for f in report.findings}
    # call length is known only after the call; too weak for the statistical test, so the template names it
    assert by_col["duration"].check == "known_leak" and by_col["duration"].action == "dropped"
    assert by_col["poutcome"].action == "warned"  # previous campaign's outcome: a name match, available before the call
    for c in ("age", "balance", "campaign", "pdays", "previous", "month", "day"):
        assert c not in by_col, f"false positive on {c}: {by_col.get(c)}"
    assert report.strategy == "stratified"
    assert all(abs(p.positive_rate - 0.117) < 0.005 for p in report.parts)
    assert "duration" not in transform.kept and "y" not in transform.kept


def test_template_words_and_cards():
    from app.templates import known_leaks, list_templates, words

    assert words("leads")["short"] == "buyers"
    assert words("custom", "churn")["short"] == "leavers"  # custom project with the churn shape speaks like churn
    assert words("custom", "regression")["short"] == "positive cases"
    assert "duration" in known_leaks("leads") and known_leaks("custom") == {}
    cards = {c["id"]: c for c in list_templates()}
    assert {"fraud", "churn", "leads"} <= set(cards)
    assert cards["leads"]["metric_line"] and len(cards["leads"]["replies"]) == 3 and cards["leads"]["goal"]


def test_profile_positive_rate_is_for_the_known_target(leads_df):
    from app.intake.metric_policy import estimate_positive_rate

    # `default` (has credit in default, 1.8% yes) is a binary column that appears before `y`
    p = profile_dataframe(leads_df, target="y", positive="yes")
    assert p.positive_rate_column == "y" and abs(p.positive_rate - 0.117) < 0.005
    assert p.target_candidates[0] == "y"
    guess = profile_dataframe(leads_df)
    assert guess.positive_rate_column == "y"
    spec = ProblemSpec(template="leads", target_column="y", positive_label="yes")
    assert abs(estimate_positive_rate(p, spec) - 0.117) < 0.005
    other = p.model_copy(update={"positive_rate_column": "default", "positive_rate": 0.018})
    assert estimate_positive_rate(other, spec) != 0.018  # a rate measured on another column is not trusted


def test_list_framing_per_template():
    from app.models_registry.promotion import list_framing

    assert list_framing("fraud")["name"] == "Fraud review queue" and list_framing("fraud")["action_label"] == "Review"
    assert list_framing("churn")["name"] == "Churn call list" and list_framing("leads")["action_label"] == "Call"
    assert list_framing("custom")["name"] == "Action list"
    cards = {c["id"]: c for c in list_templates()}
    assert cards["fraud"]["list"]["top_n"] > 0 and cards["fraud"]["description"] == "Catch more fraud without blocking good customers."
