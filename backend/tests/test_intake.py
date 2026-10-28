import asyncio
import json
from types import SimpleNamespace

import pytest

from app.intake.agent import IntakeAgent, apply_patch, parse_reply, validate_patch
from app.intake.cache import IntakeCache, cache_key, fallback_reply, normalize_text, parse_costs, parse_fpr
from app.intake.prompts import build_system_prompt
from app.models import ColumnProfile, DataProfile, IntakeMessage, ProblemSpec, SpecPatch

FRAUD_HEADER = ["TRANSACTION_ID", "TX_DATETIME", "CUSTOMER_ID", "TERMINAL_ID", "TX_AMOUNT", "TX_TIME_SECONDS", "TX_TIME_DAYS", "TX_FRAUD", "TX_FRAUD_SCENARIO"]


def fraud_profile() -> DataProfile:
    cols = []
    for name in FRAUD_HEADER:
        cols.append(
            ColumnProfile(
                name=name,
                dtype="object" if name == "TX_DATETIME" else ("float64" if name == "TX_AMOUNT" else "int64"),
                null_pct=0.0,
                unique_ratio=1.0 if name == "TRANSACTION_ID" else 0.001,
                n_unique=296928 if name == "TRANSACTION_ID" else 2,
                looks_like_time=name == "TX_DATETIME",
            )
        )
    row = {"TRANSACTION_ID": 872795, "TX_DATETIME": "2018-07-01 00:02:06", "CUSTOMER_ID": 4984, "TERMINAL_ID": 425, "TX_AMOUNT": 74.37, "TX_TIME_SECONDS": 7862526, "TX_TIME_DAYS": 91, "TX_FRAUD": 0, "TX_FRAUD_SCENARIO": 0}
    return DataProfile(n_rows=296928, n_cols=9, columns=cols, sample_rows=[row] * 20, preview_rows=[row] * 10, target_candidates=["TX_FRAUD"], positive_rate=0.0088)


def custom_profile() -> DataProfile:
    cols = [
        ColumnProfile(name="age", dtype="int64", null_pct=0.0, unique_ratio=0.05, n_unique=50),
        ColumnProfile(name="signed_at", dtype="object", null_pct=0.0, unique_ratio=0.9, n_unique=900, looks_like_time=True),
        ColumnProfile(name="renewed", dtype="int64", null_pct=0.0, unique_ratio=0.002, n_unique=2),
    ]
    rows = [{"age": 30, "signed_at": "2024-01-01", "renewed": i % 4 == 0 and 1 or 0} for i in range(20)]
    return DataProfile(n_rows=1000, n_cols=3, columns=cols, sample_rows=rows, preview_rows=rows[:10], target_candidates=["renewed"], positive_rate=None)


def run(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


async def drive(agent: IntakeAgent, template: str, profile: DataProfile, messages: list[str]):
    spec, history, responses = None, [], []
    for text in messages:
        r = await agent.turn(template=template, profile=profile, spec=spec, history=history, user_message=text)
        responses.append(r)
        spec, history = r.spec, r.history
        if r.done:
            break
    return responses


# ---------- cache ----------


def test_normalize_and_key_are_stable():
    assert normalize_text("  One in  1,000, please!  ") == "one in 1 000 please"
    assert cache_key("fraud", 0, "Hello, World") == cache_key("fraud", 0, "hello world")
    assert cache_key("fraud", 0, "hi") != cache_key("fraud", 1, "hi")
    assert cache_key("fraud", 0, "hi") != cache_key("churn", 0, "hi")


def test_cache_round_trip(tmp_path):
    c = IntakeCache("fraud", tmp_path)
    key = cache_key("fraud", 0, "go")
    assert c.get(key) is None
    c.put(key, message="hi", spec_patch={"target_column": "TX_FRAUD"}, done=False, user_text="go")
    again = IntakeCache("fraud", tmp_path)
    assert again.get(key) == {"message": "hi", "spec_patch": {"target_column": "TX_FRAUD"}, "done": False, "user_text": "go"}
    assert json.loads((tmp_path / "fraud" / "intake_cache.json").read_text())[key]["message"] == "hi"


def test_parsers():
    assert parse_fpr("1 in 1000 is fine") == 0.001
    assert parse_fpr("about 0.5%") == 0.005
    assert parse_fpr("2 per 1,000") == 0.002
    assert parse_fpr("no idea") is None
    assert parse_costs("a missed fraud costs $120 and a blocked customer about $4") == (120.0, 4.0)
    assert parse_costs("not sure") is None


# ---------- offline fallback ----------


def test_offline_fallback_completes_fraud_spec_in_three_turns(tmp_path):
    agent = IntakeAgent(client=None, offline=True, cache_root=tmp_path)
    responses = run(drive(agent, "fraud", fraud_profile(), ["We want to catch more card fraud without annoying good customers.", "1 in 1000 is fine", "a missed fraud costs about 120, a blocked customer about 4", "extra"]))
    assert len(responses) <= 3
    last = responses[-1]
    assert last.done
    assert all(r.source == "defaults" for r in responses)
    spec = last.spec
    assert spec.target_column == "TX_FRAUD"
    assert spec.positive_label == 1
    assert spec.time_column == "TX_DATETIME"
    assert spec.primary_metric == "recall_at_fpr"
    assert spec.metric_params == {"fpr": 0.001}
    assert spec.secondary_metric == "pr_auc"
    assert spec.economics == {"value_per_positive": 120.0, "cost_per_false_positive": 4.0}  # only what the user typed
    assert spec.metric_rationale
    assert len(last.history) == 6
    for r in responses:
        assert "—" not in r.message and "!" not in r.message


def test_offline_fallback_uses_user_false_alarm_rate(tmp_path):
    agent = IntakeAgent(client=None, offline=True, cache_root=tmp_path)
    responses = run(drive(agent, "fraud", fraud_profile(), ["go", "2 per 1,000", "skip"]))
    assert responses[-1].spec.metric_params == {"fpr": 0.002}
    assert "2 false alarms per 1,000" in responses[-1].spec.metric_rationale
    assert responses[-1].spec.economics is None


def test_offline_replays_cache_when_present(tmp_path):
    key = cache_key("fraud", 0, "We want to catch more card fraud")
    IntakeCache("fraud", tmp_path).put(key, message="cached reply", spec_patch={"metric_params": {"fpr": 0.003}}, done=False, user_text="x")
    agent = IntakeAgent(client=None, offline=True, cache_root=tmp_path)
    r = run(agent.turn(template="fraud", profile=fraud_profile(), spec=None, history=[], user_message="we want to catch more card fraud."))
    assert r.source == "cache"
    assert r.message == "cached reply"
    assert r.spec.metric_params == {"fpr": 0.003}
    assert not r.done


def test_custom_template_fallback_asks_for_target_then_finishes(tmp_path):
    agent = IntakeAgent(client=None, offline=True, cache_root=tmp_path)
    p = custom_profile()
    r1 = run(agent.turn(template="custom", profile=p, spec=None, history=[], user_message="help me predict renewals"))
    assert r1.spec is None and not r1.done
    assert "renewed" in r1.message
    r2 = run(agent.turn(template="custom", profile=p, spec=r1.spec, history=r1.history, user_message="the renewed column"))
    assert r2.done
    assert r2.spec.target_column == "renewed"
    assert r2.spec.positive_label == 1
    assert r2.spec.time_column == "signed_at"
    assert r2.spec.primary_metric == "recall_at_top_k"


def test_custom_template_rejects_unknown_column(tmp_path):
    agent = IntakeAgent(client=None, offline=True, cache_root=tmp_path)
    r = run(agent.turn(template="custom", profile=custom_profile(), spec=None, history=[], user_message="use the outcome column"))
    assert r.spec is None and not r.done


# ---------- parsing and patching ----------


def test_parse_reply_handles_bad_json():
    assert parse_reply("not json at all") == ("not json at all", {}, False)
    assert parse_reply('Sure: {"message": "hi", "spec_patch": {"target_column": "y"}, "done": true} tail') == ("hi", {"target_column": "y"}, True)
    assert parse_reply('{"message": 5, "spec_patch": [], "done": "yes"}')[1:] == ({}, False)


def test_validate_patch_drops_bad_fields():
    p = validate_patch({"target_column": "y", "primary_metric": "accuracy", "metric_params": {"fpr": None, "top_k": 0.2}, "economics": None, "bogus": 1})
    assert p.target_column == "y"
    assert p.primary_metric is None
    assert p.metric_params == {"top_k": 0.2}
    assert p.economics is None


def test_apply_patch_keeps_user_economics_only_and_resolves_old_keys():
    spec = ProblemSpec(template="fraud", target_column="TX_FRAUD", positive_label=1, economics={"rows_per_month": 500})
    out = apply_patch(spec, SpecPatch(economics={"cost_fn": 50, "cost_fp": 2}), template="fraud", defaults={"economics_defaults": {"cost_per_action": 0.0}})
    assert out.economics == {"rows_per_month": 500, "value_per_positive": 50, "cost_per_false_positive": 2}


def test_prompt_only_contains_sample_rows():
    p = fraud_profile()
    system = build_system_prompt(template="fraud", profile=p, defaults={"target_column": "TX_FRAUD"}, spec=None, questions_asked=0)
    assert "TX_FRAUD" in system and "looks like time" in system
    assert system.count("872795") == 20
    assert "Questions you may still ask: 3" in system


# ---------- mocked client ----------


class FakeMessages:
    def __init__(self, text: str, stop_reason: str = "end_turn"):
        self.text, self.stop_reason, self.calls = text, stop_reason, []

    async def create(self, **kw):
        self.calls.append(kw)
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=self.text)], stop_reason=self.stop_reason)


class FakeClient:
    def __init__(self, text: str, stop_reason: str = "end_turn"):
        self.messages = FakeMessages(text, stop_reason)


def test_mocked_client_bad_json_does_not_crash(tmp_path):
    client = FakeClient("{this is not json")
    agent = IntakeAgent(client=client, offline=False, cache_root=tmp_path)
    r = run(agent.turn(template="fraud", profile=fraud_profile(), spec=None, history=[], user_message="go"))
    assert r.source == "llm"
    assert r.message == "{this is not json"
    assert r.spec_patch == SpecPatch()
    assert r.spec.target_column == "TX_FRAUD"
    assert not r.done
    call = client.messages.calls[0]
    assert call["output_config"]["format"]["type"] == "json_schema"
    assert call["messages"][-1] == {"role": "user", "content": "go"}
    assert len(IntakeCache("fraud", tmp_path)) == 1


def test_mocked_client_good_json_is_cached_and_policy_overrides(tmp_path):
    reply = json.dumps({"message": "Fine. Done.", "spec_patch": {"primary_metric": "recall_at_top_k", "metric_params": {"fpr": 0.002, "top_k": None}, "economics": {"monthly_volume": 1000, "cost_fn": 10, "cost_fp": 1}}, "done": True})
    client = FakeClient(reply)
    agent = IntakeAgent(client=client, offline=False, cache_root=tmp_path)
    r = run(agent.turn(template="fraud", profile=fraud_profile(), spec=None, history=[], user_message="all good"))
    assert r.source == "llm" and r.done
    assert r.spec.primary_metric == "recall_at_fpr"
    assert r.spec.metric_params == {"fpr": 0.002}
    assert r.spec.economics == {"rows_per_month": 1000, "value_per_positive": 10, "cost_per_false_positive": 1}
    cached = IntakeCache("fraud", tmp_path).get(cache_key("fraud", 0, "all good"))
    assert cached["message"] == "Fine. Done."
    # offline replay of the same text yields the same result from cache
    replay = IntakeAgent(client=None, offline=True, cache_root=tmp_path)
    r2 = run(replay.turn(template="fraud", profile=fraud_profile(), spec=None, history=[], user_message="All good."))
    assert r2.source == "cache" and r2.spec.metric_params == {"fpr": 0.002}


def test_mocked_client_failure_falls_back_to_defaults(tmp_path):
    class Boom:
        async def create(self, **kw):
            raise RuntimeError("network down")

    client = SimpleNamespace(messages=Boom())
    agent = IntakeAgent(client=client, offline=False, cache_root=tmp_path)
    r = run(agent.turn(template="fraud", profile=fraud_profile(), spec=None, history=[], user_message="go"))
    assert r.source == "defaults"
    assert r.spec.target_column == "TX_FRAUD"


def test_done_forced_after_three_assistant_turns_when_complete(tmp_path):
    client = FakeClient(json.dumps({"message": "one more thing?", "spec_patch": {}, "done": False}))
    agent = IntakeAgent(client=client, offline=False, cache_root=tmp_path)
    history = [IntakeMessage(role="user", content="a"), IntakeMessage(role="assistant", content="q1"), IntakeMessage(role="user", content="b"), IntakeMessage(role="assistant", content="q2")]
    r = run(agent.turn(template="fraud", profile=fraud_profile(), spec=None, history=history, user_message="c"))
    assert r.done
