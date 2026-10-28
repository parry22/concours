"""Sensitive attributes (set aside, fairness report) and repeated entities (group split)."""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.models import ProblemSpec
from app.packager.checks.repeated_entity import candidates
from app.packager.checks.sensitive import detect, trait_by_name
from app.packager.fairness import report as fairness_report
from app.packager.protect import protect
from app.packager.split import split_grouped


def _people(n: int = 2000, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    patient = rng.integers(0, n // 3, n)  # about three visits per patient
    x = rng.normal(size=n)
    return pd.DataFrame({
        "encounter_id": np.arange(n) * 7 + 11,
        "patient_nbr": patient,
        "Gender": rng.choice(["Male", "Female"], n),
        "col_r": rng.choice(["Caucasian", "AfricanAmerican", "Hispanic", "Other"], n),
        "AGE": rng.integers(18, 90, n),
        "MaritalStatus": rng.choice(["Married", "Single", "Divorced"], n),
        "visits": rng.poisson(2, n),
        "x": x,
        "y": np.where(x + rng.normal(scale=0.8, size=n) > 1.2, "yes", "no"),
    })


def test_detects_by_name_and_by_values():
    df = _people(300)
    found = detect(df, {"y"})
    assert found["Gender"] == ("gender", "name")
    assert found["AGE"] == ("age", "name")
    assert found["MaritalStatus"] == ("marital status", "name")
    assert found["col_r"] == ("race", "values")  # no telling name, the values give it away
    assert "visits" not in found and "x" not in found and "patient_nbr" not in found


@pytest.mark.parametrize("name", ["usage", "average_bill", "page_views", "mileage", "Message", "storage_gb"])
def test_age_inside_other_words_is_not_sensitive(name: str):
    assert trait_by_name(name) is None


def test_repeated_entity_found_but_unique_ids_and_categories_are_not():
    df = _people(3000)
    df["state_id"] = np.random.default_rng(1).integers(0, 50, len(df))  # a category: few values
    got = [c for c, *_ in candidates(df, [c for c in df.columns if c != "y"], None)]
    assert got == ["patient_nbr"]


def test_group_split_keeps_each_entity_on_one_side():
    df = _people(3000)
    s = split_grouped(df, "y", "patient_nbr")
    a, b, c = (set(p["patient_nbr"]) for p in (s.train, s.leaderboard, s.holdout))
    assert not (a & b) and not (a & c) and not (b & c)
    assert s.strategy == "group"
    total = len(df)
    assert abs(len(s.train) / total - 0.70) < 0.03 and abs(len(s.holdout) / total - 0.20) < 0.03


def test_protect_sets_aside_sensitive_columns_and_splits_by_entity(tmp_path: Path):
    df = _people(3000)
    spec = ProblemSpec(template="custom", target_column="y", positive_label="yes", primary_metric="recall_at_top_k", metric_params={"top_k": 0.1})
    report, transform = protect(df, spec, tmp_path)
    sensitive = {"Gender", "col_r", "AGE", "MaritalStatus"}
    assert sensitive == set(report.set_aside_columns)
    assert not sensitive & set(transform.kept)
    assert report.strategy == "group" and report.group_column == "patient_nbr"
    assert "patient_nbr" not in transform.kept and "encounter_id" not in transform.kept
    f = {x.check: x for x in report.findings}
    assert f["sensitive"].severity == "medium" and f["sensitive"].action == "set_aside"
    assert f["repeated_entity"].severity == "high" and f["repeated_entity"].action == "group_split"
    assert "same" in f["repeated_entity"].reason and "better than reality" in f["repeated_entity"].reason
    # solver files carry neither the sensitive columns nor the entity key
    for name in ("train", "leaderboard", "holdout"):
        cols = set(pd.read_csv(tmp_path / f"{name}.csv", nrows=1).columns)
        assert not (sensitive | {"patient_nbr"}) & cols
    side = pd.read_csv(tmp_path / "holdout_sensitive.csv")
    assert set(side.columns) == sensitive
    assert len(side) == len(pd.read_csv(tmp_path / "holdout_labels.csv"))


def test_fairness_report_per_group(tmp_path: Path):
    df = _people(4000, seed=3)
    spec = ProblemSpec(template="custom", target_column="y", positive_label="yes", primary_metric="recall_at_top_k", metric_params={"top_k": 0.1})
    report, _ = protect(df, spec, tmp_path)
    y = pd.read_csv(tmp_path / "holdout_labels.csv")["label"].to_numpy()
    scores = pd.read_csv(tmp_path / "holdout.csv")["x"].to_numpy()
    traits = {f.column: f.evidence["trait"] for f in report.findings if f.check == "sensitive"}
    fr = fairness_report(tmp_path, spec, scores, y, traits, {"Gender": {"Male": "Men", "Female": "Women"}}, model_version=1)
    assert fr is not None and fr.selected == int(np.ceil(0.1 * len(y)))
    by = {c.column: c for c in fr.columns}
    assert {g.group for g in by["Gender"].groups} == {"Men", "Women"}
    assert {g.group for g in by["AGE"].groups} <= {"Under 25", "25 to 34", "35 to 44", "45 to 54", "55 to 64", "65 and over"}
    for c in fr.columns:
        assert sum(g.rows for g in c.groups) == len(y)
        assert sum(g.selected for g in c.groups) == fr.selected
        for g in c.groups:
            assert 0 <= g.selection_rate <= 1 and (g.hit_rate is None or 0 <= g.hit_rate <= 1)
        assert c.note


def test_templates_people_framing():
    from app.templates import list_templates, load_defaults

    cards = {c["id"]: c for c in list_templates()}
    for tid, list_name, action in (("payments", "Early outreach list", "Call"), ("readmissions", "Follow-up list", "Call"),
                                   ("attrition", "Retention conversations", "Check in")):
        assert cards[tid]["list"]["name"] == list_name and cards[tid]["list"]["action_label"] == action
        assert cards[tid]["people"] is True
    assert load_defaults("attrition")["dataset_env"] == "CONCOURS_ATTRITION_CSV"
    assert cards["attrition"]["source_url"]


def test_readmissions_template_groups_by_patient(readmissions_df, tmp_path: Path):
    from app.templates import spec_from_defaults

    report, transform = protect(readmissions_df, spec_from_defaults("readmissions"), tmp_path)
    assert report.strategy == "group" and report.group_column == "patient_nbr"
    assert {"race", "gender", "age"} <= set(report.set_aside_columns)
    assert "encounter_id" in report.dropped_columns
    tr = pd.read_csv(tmp_path / "train.csv", usecols=["num_lab_procedures"])
    assert len(tr) > 0


DECISION = re.compile(r"\b(reject\w*|den(y|ies|ied|ial)|declin\w*|approv\w*|terminat\w*|fire[ds]?|firing|flag\w*|disqualif\w*|blacklist\w*)\b", re.I)


@pytest.mark.parametrize("template", ["payments", "readmissions", "attrition"])
def test_people_templates_use_support_language(template: str):
    """Text the backend writes for a people template (headline, improvement line, list framing, value labels)."""
    from app.models_registry.promotion import list_framing
    from app.shared.translate import headline, improvement_line, metric_label, result_short, short_label
    from app.templates import load_defaults, spec_from_defaults
    from app.value.params import LABELS

    spec = spec_from_defaults(template)
    cfg = load_defaults(template)
    texts = [headline(spec, 0.42), improvement_line(spec, 0.30, 0.42), result_short(spec, 0.30, 0.42), metric_label(spec), short_label(spec)]
    texts += [str(v) for v in list_framing(template, spec).values()]
    texts += list(LABELS[cfg["business_template"]].values())
    hits = [t for t in texts if DECISION.search(t)]
    assert not hits, hits
