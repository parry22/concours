"""Template defaults (data/templates/<name>/defaults.json).

A template folder carries the dataset, the spec defaults, the plain-language words every screen uses for
that problem (`words`), the home-card line (`metric_line`), the scripted intake replies (`replies`) and
columns known to leak (`known_leaks`). `business_template` is the metric shape (fraud, churn, regression)
and is what the value model and the metric policy key on; the words come from the template itself.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config import TEMPLATES_DIR
from app.models import ProblemSpec

CARD_FIELDS = ("name", "description", "label", "icon", "metric_line", "intake_goal", "replies", "list")

# Words when neither the template nor the shape has a folder (custom project with an unknown shape).
DEFAULT_WORDS: dict[str, str] = {
    "positive": "positive cases",
    "negative": "other rows",
    "short": "positive cases",
    "past": "positive cases",
    "future": "rows will be positive",
    "event": "a confirmed case",
    "team": "team",
    "about_to": "about to happen",
}


def list_templates() -> list[dict[str, Any]]:
    out = []
    for d in sorted(TEMPLATES_DIR.iterdir()):
        f = d / "defaults.json"
        if f.exists():
            cfg = json.loads(f.read_text())
            card = {k: cfg.get(k) for k in CARD_FIELDS}
            card["goal"] = card.pop("intake_goal")
            out.append({"id": d.name, **card, "has_dataset": (d / cfg["dataset"]).exists()})
    return out


def load_defaults(template: str) -> dict[str, Any] | None:
    f = TEMPLATES_DIR / template / "defaults.json"
    return json.loads(f.read_text()) if f.exists() else None


def words(template: str | None, business_template: str | None = None) -> dict[str, str]:
    """Plain words for a problem: the template's own, else those of the template that shares its metric shape
    (a custom project with the churn shape speaks like churn), else generic."""
    for name in (template, business_template):
        cfg = load_defaults(name) if name else None
        if cfg and cfg.get("words"):
            return {**DEFAULT_WORDS, **cfg["words"]}
    return dict(DEFAULT_WORDS)


def rate_hint(template: str | None) -> float | None:
    cfg = load_defaults(template) if template else None
    return float(cfg["rate_hint"]) if cfg and cfg.get("rate_hint") is not None else None


def known_leaks(template: str | None) -> dict[str, str]:
    cfg = load_defaults(template) if template else None
    return dict(cfg.get("known_leaks") or {}) if cfg else {}


def dataset_path(template: str) -> Path | None:
    cfg = load_defaults(template)
    if not cfg:
        return None
    p = TEMPLATES_DIR / template / cfg["dataset"]
    return p if p.exists() else None


def spec_from_defaults(template: str) -> ProblemSpec | None:
    cfg = load_defaults(template)
    if not cfg:
        return None
    return ProblemSpec(
        template=template,  # type: ignore[arg-type]
        target_column=cfg["target_column"],
        positive_label=cfg.get("positive_label"),
        time_column=cfg.get("time_column"),
        primary_metric=cfg["primary_metric"],
        metric_params=cfg["metric_params"],
        secondary_metric=cfg.get("secondary_metric"),
        business_template=cfg["business_template"],
    )
