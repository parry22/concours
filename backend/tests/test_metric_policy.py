from app.intake.metric_policy import decide_metric, spec_is_complete
from app.models import ColumnProfile, DataProfile, ProblemSpec


def col(name, dtype="int64", n_unique=2, unique_ratio=0.0, **kw):
    return ColumnProfile(name=name, dtype=dtype, null_pct=0.0, unique_ratio=unique_ratio, n_unique=n_unique, **kw)


def profile(columns, positive_rate=None, sample_rows=None):
    return DataProfile(
        n_rows=1000,
        n_cols=len(columns),
        columns=columns,
        sample_rows=sample_rows or [],
        preview_rows=[],
        positive_rate=positive_rate,
    )


FRAUD_PROFILE = profile(
    [
        col("TRANSACTION_ID", n_unique=1000, unique_ratio=1.0),
        col("TX_DATETIME", dtype="object", n_unique=990, unique_ratio=0.99, looks_like_time=True),
        col("TX_AMOUNT", dtype="float64", n_unique=900, unique_ratio=0.9),
        col("TX_FRAUD"),
    ],
    positive_rate=0.0088,
)

CHURN_PROFILE = profile([col("Call  Failure", n_unique=30, unique_ratio=0.01), col("Churn")], positive_rate=0.157)


def test_fraud_like_picks_recall_at_fpr():
    spec = decide_metric(FRAUD_PROFILE, ProblemSpec(template="fraud", target_column="TX_FRAUD", positive_label=1))
    assert spec.primary_metric == "recall_at_fpr"
    assert spec.metric_params == {"fpr": 0.001}
    assert spec.secondary_metric == "pr_auc"
    assert spec.business_template == "fraud"
    assert spec.metric_rationale == (
        "Fewer than 1 in 100 rows are fraud, so we measure how much fraud is caught at 1 false alarm per 1,000 good transactions."
    )


def test_churn_like_picks_recall_at_top_k():
    spec = decide_metric(CHURN_PROFILE, ProblemSpec(template="churn", target_column="Churn", positive_label=1))
    assert spec.primary_metric == "recall_at_top_k"
    assert spec.metric_params == {"top_k": 0.10}
    assert spec.secondary_metric == "roc_auc"
    assert spec.business_template == "churn"
    assert "riskiest 10% of customers" in spec.metric_rationale
    assert "AUC" not in spec.metric_rationale


def test_regression_picks_wape():
    p = profile([col("price", dtype="float64", n_unique=800, unique_ratio=0.8)])
    spec = decide_metric(p, ProblemSpec(template="custom", target_column="price", task_type="regression"))
    assert (spec.primary_metric, spec.secondary_metric) == ("wape", "mae")
    assert spec.positive_label is None
    assert spec.metric_params == {}


def test_numeric_target_with_many_values_is_treated_as_regression():
    p = profile([col("amount", dtype="float64", n_unique=500, unique_ratio=0.5)])
    spec = decide_metric(p, ProblemSpec(template="custom", target_column="amount"))
    assert spec.task_type == "regression"
    assert spec.primary_metric == "wape"


def test_overrides_wrong_llm_proposal():
    wrong = ProblemSpec(
        template="fraud",
        target_column="TX_FRAUD",
        positive_label=1,
        primary_metric="recall_at_top_k",
        metric_params={"top_k": 0.3},
        secondary_metric="roc_auc",
        business_template="churn",
    )
    spec = decide_metric(FRAUD_PROFILE, wrong)
    assert spec.primary_metric == "recall_at_fpr"
    assert spec.metric_params == {"fpr": 0.001}
    assert spec.secondary_metric == "pr_auc"
    assert spec.business_template == "fraud"


def test_explicit_positive_rate_kwarg_wins():
    spec = decide_metric(FRAUD_PROFILE, ProblemSpec(template="fraud", target_column="TX_FRAUD", positive_label=1), positive_rate=0.3)
    assert spec.primary_metric == "recall_at_top_k"


def test_fpr_from_intake_is_kept_and_clamped():
    base = ProblemSpec(template="fraud", target_column="TX_FRAUD", positive_label=1)
    assert decide_metric(FRAUD_PROFILE, base.model_copy(update={"metric_params": {"fpr": 0.002}})).metric_params == {"fpr": 0.002}
    assert decide_metric(FRAUD_PROFILE, base.model_copy(update={"metric_params": {"fpr": 0.5}})).metric_params == {"fpr": 0.05}
    assert decide_metric(FRAUD_PROFILE, base.model_copy(update={"metric_params": {"fpr": 0.0}})).metric_params == {"fpr": 0.0001}
    assert decide_metric(FRAUD_PROFILE, base.model_copy(update={"metric_params": {"fpr": "junk"}})).metric_params == {"fpr": 0.001}


def test_top_k_clamped():
    base = ProblemSpec(template="churn", target_column="Churn", positive_label=1)
    assert decide_metric(CHURN_PROFILE, base.model_copy(update={"metric_params": {"top_k": 0.9}})).metric_params == {"top_k": 0.5}
    assert decide_metric(CHURN_PROFILE, base.model_copy(update={"metric_params": {"top_k": 0.001}})).metric_params == {"top_k": 0.01}


def test_rationale_numbers_follow_params():
    spec = decide_metric(FRAUD_PROFILE, ProblemSpec(template="fraud", target_column="TX_FRAUD", positive_label=1, metric_params={"fpr": 0.005}))
    assert "5 false alarms per 1,000 good transactions" in spec.metric_rationale


def test_positive_rate_estimated_from_sample_rows_when_profile_lacks_it():
    rows = [{"y": 1}] * 5 + [{"y": 0}] * 15
    p = profile([col("y")], positive_rate=None, sample_rows=rows)
    spec = decide_metric(p, ProblemSpec(template="custom", target_column="y", positive_label=1))
    assert spec.primary_metric == "recall_at_top_k"


def test_spec_is_complete():
    assert not spec_is_complete(None)
    assert not spec_is_complete(ProblemSpec(target_column="y"))
    assert not spec_is_complete(ProblemSpec(target_column="y", positive_label=1, metric_params={}))
    assert spec_is_complete(ProblemSpec(target_column="y", positive_label=1, metric_params={"fpr": 0.001}))
    assert spec_is_complete(ProblemSpec(target_column="y", task_type="regression", primary_metric="wape"))
