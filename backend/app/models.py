"""Pydantic and SQLModel models. These are the contract between backend and frontend."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field
from sqlmodel import Field as SQLField
from sqlmodel import SQLModel

Template = Literal["fraud", "churn", "custom"]
Stage = Literal["upload", "intake", "protect", "arena", "serve", "launch"]
Validation = Literal["pass", "fail", "not_run"]


# ---------- Problem spec ----------


class ProblemSpec(BaseModel):
    template: Template = "custom"
    task_type: Literal["binary", "regression"] = "binary"
    target_column: str
    positive_label: str | int | None = None
    time_column: str | None = None
    primary_metric: Literal["recall_at_fpr", "recall_at_top_k", "wape"] = "recall_at_fpr"
    metric_params: dict[str, Any] = Field(default_factory=dict)
    secondary_metric: str | None = None
    metric_rationale: str = ""
    business_template: str = "fraud"
    constraints: dict[str, Any] = Field(
        default_factory=lambda: {
            "max_ms_per_row": 5,
            "allowed_libs": ["scikit-learn", "lightgbm", "xgboost", "pandas", "numpy"],
        }
    )
    economics: dict[str, Any] | None = None


class SpecPatch(BaseModel):
    """Partial ProblemSpec: every field optional. Applied by the intake agent."""

    template: Template | None = None
    task_type: Literal["binary", "regression"] | None = None
    target_column: str | None = None
    positive_label: str | int | None = None
    time_column: str | None = None
    primary_metric: Literal["recall_at_fpr", "recall_at_top_k", "wape"] | None = None
    metric_params: dict[str, Any] | None = None
    secondary_metric: str | None = None
    metric_rationale: str | None = None
    business_template: str | None = None
    constraints: dict[str, Any] | None = None
    economics: dict[str, Any] | None = None


# ---------- Data profile ----------


class ColumnProfile(BaseModel):
    name: str
    dtype: str
    null_pct: float
    unique_ratio: float
    n_unique: int
    min: float | str | None = None
    max: float | str | None = None
    looks_like_time: bool = False
    pii_masked: bool = False


class DataProfile(BaseModel):
    n_rows: int
    n_cols: int
    columns: list[ColumnProfile]
    sample_rows: list[dict[str, Any]]  # 20 rows, PII masked
    preview_rows: list[dict[str, Any]]  # 10 rows for the upload screen, PII masked
    target_candidates: list[str] = Field(default_factory=list)
    positive_rate: float | None = None


# ---------- Protection ----------


class Finding(BaseModel):
    check: str
    severity: Literal["high", "medium", "info"]
    column: str | None
    reason: str
    action: Literal["dropped", "masked", "removed_rows", "warned", "resplit"]
    evidence: dict[str, Any] = Field(default_factory=dict)


class SplitPart(BaseModel):
    name: Literal["train", "leaderboard", "holdout"]
    rows: int
    positives: int
    positive_rate: float
    time_min: str | None = None
    time_max: str | None = None


class ProtectReport(BaseModel):
    strategy: Literal["time", "stratified"]
    seed: int = 42
    parts: list[SplitPart]
    findings: list[Finding]
    kept_columns: list[str]
    dropped_columns: list[str]
    masked_columns: list[str]
    rows_removed: int = 0
    checksums: dict[str, str] = Field(default_factory=dict)  # file -> sha256


# ---------- Arena ----------


class SubmissionOut(BaseModel):
    id: str
    solver: str
    status: Literal["queued", "running", "scored", "failed"]
    public_score: float | None = None
    private_score: float | None = None  # null until finalized
    secondary_public: float | None = None
    secondary_private: float | None = None
    business_value: str | None = None
    logs_path: str
    error: str | None = None
    eval_seconds: float | None = None
    rank: int | None = None
    is_leader: bool = False


class LeaderboardOut(BaseModel):
    project_id: str
    finalized: bool
    submissions: list[SubmissionOut]
    leader: SubmissionOut | None = None
    baseline: SubmissionOut | None = None
    business_card: str | None = None
    raw_metric_line: str | None = None
    savings_line: str | None = None
    savings_formula: str | None = None
    takeover_margin: float = 0.01


# ---------- Intake ----------


class IntakeMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class IntakeRequest(BaseModel):
    message: str


class IntakeResponse(BaseModel):
    message: str
    spec_patch: SpecPatch
    spec: ProblemSpec | None
    done: bool
    source: Literal["llm", "cache", "defaults"]
    history: list[IntakeMessage]


# ---------- Package / validation ----------


class ValidationStep(BaseModel):
    name: str
    status: Literal["pass", "fail", "not_run"]
    log: str = ""


class PackageOut(BaseModel):
    competition_dir: str
    competition_id: str
    validation: Validation
    steps: list[ValidationStep]
    files: list[str]


# ---------- Project ----------


class ProjectCreate(BaseModel):
    name: str | None = None
    template: Template = "custom"


class ProjectOut(BaseModel):
    id: str
    name: str
    template: Template
    stage: Stage
    spec: ProblemSpec | None
    apex_validation: Validation
    created_at: datetime
    has_data: bool
    profile: DataProfile | None = None
    protect: ProtectReport | None = None
    finalized: bool = False
    winner_solver: str | None = None


# ---------- SQLModel tables ----------


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ProjectRow(SQLModel, table=True):
    __tablename__ = "project"

    id: str = SQLField(default_factory=lambda: uuid.uuid4().hex[:12], primary_key=True)
    name: str
    template: str = "custom"
    stage: str = "upload"
    spec_json: str | None = None
    profile_json: str | None = None
    protect_json: str | None = None
    intake_json: str = "[]"
    apex_validation: str = "not_run"
    package_json: str | None = None
    finalized: bool = False
    winner_solver: str | None = None
    created_at: datetime = SQLField(default_factory=_now)

    def spec(self) -> ProblemSpec | None:
        return ProblemSpec.model_validate_json(self.spec_json) if self.spec_json else None

    def set_spec(self, spec: ProblemSpec | None) -> None:
        self.spec_json = spec.model_dump_json() if spec else None

    def profile(self) -> DataProfile | None:
        return DataProfile.model_validate_json(self.profile_json) if self.profile_json else None

    def protect(self) -> ProtectReport | None:
        return ProtectReport.model_validate_json(self.protect_json) if self.protect_json else None

    def intake(self) -> list[IntakeMessage]:
        return [IntakeMessage(**m) for m in json.loads(self.intake_json)]

    def set_intake(self, msgs: list[IntakeMessage]) -> None:
        self.intake_json = json.dumps([m.model_dump() for m in msgs])

    def to_out(self) -> ProjectOut:
        return ProjectOut(
            id=self.id,
            name=self.name,
            template=self.template,  # type: ignore[arg-type]
            stage=self.stage,  # type: ignore[arg-type]
            spec=self.spec(),
            apex_validation=self.apex_validation,  # type: ignore[arg-type]
            created_at=self.created_at,
            has_data=self.profile_json is not None,
            profile=self.profile(),
            protect=self.protect(),
            finalized=self.finalized,
            winner_solver=self.winner_solver,
        )


class SubmissionRow(SQLModel, table=True):
    __tablename__ = "submission"

    id: str = SQLField(default_factory=lambda: uuid.uuid4().hex[:12], primary_key=True)
    project_id: str = SQLField(index=True)
    solver: str
    status: str = "queued"
    public_score: float | None = None
    private_score: float | None = None
    secondary_public: float | None = None
    secondary_private: float | None = None
    logs_path: str = ""
    error: str | None = None
    eval_seconds: float | None = None
    data_hash: str = ""
    result_json: str | None = None
    created_at: datetime = SQLField(default_factory=_now)
