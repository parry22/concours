"""Template defaults (data/templates/<name>/defaults.json)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config import TEMPLATES_DIR
from app.models import ProblemSpec


def list_templates() -> list[dict[str, Any]]:
    out = []
    for d in sorted(TEMPLATES_DIR.iterdir()):
        f = d / "defaults.json"
        if f.exists():
            cfg = json.loads(f.read_text())
            out.append({"id": d.name, "name": cfg["name"], "description": cfg["description"], "has_dataset": (d / cfg["dataset"]).exists()})
    return out


def load_defaults(template: str) -> dict[str, Any] | None:
    f = TEMPLATES_DIR / template / "defaults.json"
    return json.loads(f.read_text()) if f.exists() else None


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
