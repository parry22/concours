"""Business lines: every number comes from code and reads as an outcome, never as a metric name."""
from app.models import ProblemSpec
from app.shared import translate as T

FRAUD = ProblemSpec(template="fraud", target_column="TX_FRAUD", positive_label=1, primary_metric="recall_at_fpr", metric_params={"fpr": 0.001}, business_template="fraud")
LEADS = ProblemSpec(template="leads", target_column="y", positive_label="yes", primary_metric="recall_at_top_k", metric_params={"top_k": 0.1}, business_template="churn")


def test_headline_and_improvement():
    assert T.headline(FRAUD, 0.84) == "Fraud caught at 1 false alarm per 1,000 good transactions: 84%"
    assert T.improvement_line(FRAUD, 0.61, 0.84) == "61% to 84% since your first model"
    assert T.improvement_line(FRAUD, 0.61, 0.61) == "Your first model"
    assert T.headline(LEADS, 0.52) == "Buyers reached in your top 10%: 52%"


def test_result_short_for_tables():
    assert T.result_short(LEADS, 0.34, 0.52) == "Buyers reached: 34% to 52%"
    assert T.result_short(LEADS, None, 0.52) == "Buyers reached: 52%"
    assert T.result_short(FRAUD, 0.22, 0.30) == "Fraud caught: 22% to 30%"


def test_improvement_rel_is_direction_aware():
    assert abs(T.improvement_rel(FRAUD, 0.2, 0.3) - 0.5) < 1e-9
    wape = ProblemSpec(template="custom", target_column="y", primary_metric="wape", business_template="regression")
    assert abs(T.improvement_rel(wape, 0.30, 0.18) - 0.4) < 1e-9


def test_no_algorithm_names_in_business_lines():
    for line in (T.headline(FRAUD, 0.5), T.metric_label(LEADS), T.result_short(FRAUD, 0.1, 0.2), T.business_card(FRAUD, 0.1, 0.2)):
        assert not any(w in line.lower() for w in ("lightgbm", "logistic", "xgboost", "recall", "auc"))
