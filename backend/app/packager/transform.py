"""transform.json: what was dropped, masked, kept. Applied identically by packager, player and serving."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import BaseModel, Field

from app.packager.pii import hash_value


class Transform(BaseModel):
    target_column: str
    positive_label: Any = None
    time_column: str | None = None
    kept: list[str] = Field(default_factory=list)
    dropped: list[str] = Field(default_factory=list)
    masked: list[str] = Field(default_factory=list)  # hashed, still present
    reasons: dict[str, str] = Field(default_factory=dict)

    def apply(self, df: pd.DataFrame, *, require_target: bool = False) -> pd.DataFrame:
        """Return features (+ target if present). Unknown columns are dropped; missing kept columns raise."""
        missing = [c for c in self.kept if c not in df.columns]
        if missing:
            raise ValueError(f"Uploaded file is missing columns the model needs: {missing}")
        if require_target and self.target_column not in df.columns:
            raise ValueError(f"Missing target column {self.target_column}")
        cols = list(self.kept)
        if self.target_column in df.columns:
            cols.append(self.target_column)
        out = df[cols].copy()
        for c in self.masked:
            if c in out.columns:
                out[c] = out[c].map(hash_value)
        return out

    def save(self, path: Path) -> None:
        path.write_text(self.model_dump_json(indent=2))

    @classmethod
    def load(cls, path: Path) -> "Transform":
        return cls.model_validate_json(Path(path).read_text())


def features_of(t: Transform) -> list[str]:
    return [c for c in t.kept if c != t.target_column]


def load_json(path: Path) -> dict:
    return json.loads(Path(path).read_text())
