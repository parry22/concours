import pandas as pd

from app.models import ProblemSpec
from app.packager.checks import constant, cross_split_dup, id_like, pii, post_outcome_name, target_leak, temporal
from app.packager.checks.base import CheckContext
from app.packager.split import Split, split_stratified
from app.packager.protect import run_column_checks


def ctx_for(df, target="target", positive=1, time_column="event_time"):
    return CheckContext(df=df, target=target, positive=positive, time_column=time_column)


def test_constant(toy_df):
    c = ctx_for(toy_df)
    constant.run(c)
    assert "const" in c.dropped and "card_number" in c.dropped  # card_number is constant too
    assert all(f.severity == "info" for f in c.findings)


def test_id_like_drops_counter_and_skips_time(toy_df):
    c = ctx_for(toy_df)
    id_like.run(c)
    assert "row_id" in c.dropped
    assert "event_time" not in c.dropped
    assert "amount" not in c.dropped


def test_pii_masks_email_and_card(toy_df):
    c = ctx_for(toy_df)
    pii.run(c)
    kinds = {f.column: f.evidence["kind"] for f in c.findings}
    assert kinds["email"] == "email" and kinds["card_number"] == "card"
    by = {f.column: f.action for f in c.findings}
    assert by["email"] == "masked"
    assert by["card_number"] == "dropped" and "card_number" in c.dropped  # card numbers never leave, even hashed


def test_post_outcome_name_warns(toy_df):
    c = ctx_for(toy_df)
    post_outcome_name.run(c)
    assert [f.column for f in c.findings] == ["dispute_status"]
    assert c.findings[0].action == "warned"


def test_target_leak_drops_only_the_leak(toy_df):
    c = ctx_for(toy_df)
    target_leak.run(c)
    assert "dispute_status" in c.dropped
    assert "signal" not in c.dropped and "amount" not in c.dropped
    f = [f for f in c.findings if f.column == "dispute_status"][0]
    assert f.severity == "high" and "cheat" in f.reason


def test_column_checks_merge_warn_into_drop(toy_df):
    spec = ProblemSpec(target_column="target", positive_label=1, time_column="event_time")
    c = run_column_checks(toy_df, spec)
    cols = [(f.column, f.action) for f in c.findings]
    assert ("dispute_status", "dropped") in cols
    assert ("dispute_status", "warned") not in cols


def test_cross_split_dup_removes_from_train():
    df = pd.DataFrame({"a": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10] * 10, "b": list(range(100)), "target": [0, 1] * 50})
    df.loc[0:19, ["a", "b"]] = 0  # 20 identical rows -> some land in train and some in holdout
    s = split_stratified(df, "target")
    findings = []
    n = cross_split_dup.run(s, ["a", "b"], findings)
    assert n > 0 and findings[0].action == "removed_rows"
    assert len(s.train) == 70 - n


def test_temporal_resplits_when_shuffled():
    df = pd.DataFrame({"t": pd.date_range("2024-01-01", periods=100, freq="D").astype(str), "x": range(100), "target": [0, 1] * 50})
    s = split_stratified(df, "target")  # ignores time -> leaks
    findings = []
    s2 = temporal.run(s, "t", findings)
    assert findings and findings[0].action == "resplit"
    assert pd.to_datetime(s2.train["t"]).max() <= pd.to_datetime(s2.holdout["t"]).min()
    assert not temporal.run(s2, "t", [])  is None


def test_arena_cache_requires_same_scoring_rule():
    import json

    from app.arena.service import _same_rule
    from app.models import ProblemSpec, SubmissionRow

    meta = {"primary_metric": "recall_at_fpr", "metric_params": {"fpr": 0.001}, "secondary_metric": "pr_auc"}
    sub = SubmissionRow(project_id="p", solver="lgbm_default", result_json=json.dumps({"raw_scores": [0.1], "metadata": meta}))
    fraud = ProblemSpec(target_column="t", primary_metric="recall_at_fpr", metric_params={"fpr": 0.001}, secondary_metric="pr_auc")
    leads = ProblemSpec(target_column="t", primary_metric="recall_at_top_k", metric_params={"top_k": 0.1}, secondary_metric="roc_auc")
    assert _same_rule(sub, fraud) and not _same_rule(sub, leads)
    assert not _same_rule(SubmissionRow(project_id="p", solver="x", result_json=None), fraud)
