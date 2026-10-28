"""Pydantic and SQLModel models. These are the contract between backend and frontend."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field
from sqlmodel import Field as SQLField
from sqlmodel import SQLModel

Template = Literal["fraud", "churn", "leads", "payments", "readmissions", "attrition", "custom"]
Stage = Literal["upload", "intake", "protect", "model", "improve", "launch"]
VersionSource = Literal["baseline", "local_contest", "apex_contest"]
Health = Literal["unknown", "healthy", "slipping"]
ModelStatus = Literal["improving", "healthy", "slipping", "none"]
Validation = Literal["pass", "fail", "not_run"]


# ---------- Problem spec ----------


class ProblemSpec(BaseModel):
    template: Template = "custom"
    task_type: Literal["binary", "regression"] = "binary"
    target_column: str
    positive_label: str | int | None = None
    time_column: str | None = None
    primary_metric: Literal["recall_at_fpr", "recall_at_top_k", "wape", "fraud_amount_per_day"] = "recall_at_fpr"
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
    primary_metric: Literal["recall_at_fpr", "recall_at_top_k", "wape", "fraud_amount_per_day"] | None = None
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
    positive_rate_column: str | None = None  # the column positive_rate was measured on


# ---------- Protection ----------


class Finding(BaseModel):
    check: str
    severity: Literal["high", "medium", "info"]
    column: str | None
    reason: str
    action: Literal["dropped", "masked", "removed_rows", "warned", "resplit", "set_aside", "group_split", "hashed", "relabeled", "embargoed"]
    evidence: dict[str, Any] = Field(default_factory=dict)


class SplitPart(BaseModel):
    name: Literal["train", "leaderboard", "holdout"]
    rows: int
    positives: int
    positive_rate: float
    time_min: str | None = None
    time_max: str | None = None


class MaturitySummary(BaseModel):
    """Late labels: what was knowable when. Days are ISO dates."""

    as_of: str  # the evaluation date ("today")
    label_delay_days: int
    label_time_simulated: bool
    train_end: str  # the training cutoff
    embargo_start: str
    embargo_end: str
    leaderboard_start: str
    holdout_start: str
    holdout_end: str
    immature_start: str  # newest days: no mature labels yet, used only for today's queue and drift
    frauds_in_train: int  # all frauds in the training window
    frauds_unconfirmed_in_train: int  # confirmed after the training cutoff, so label 0 for training
    frauds_unconfirmed_at_eval: int  # in the evaluation windows, still unconfirmed at the as-of date
    embargo_rows: int
    immature_rows: int
    analyst_labels: int = 0


class ProtectReport(BaseModel):
    strategy: Literal["time", "stratified", "group", "time_embargo"]
    seed: int = 42
    parts: list[SplitPart]
    findings: list[Finding]
    kept_columns: list[str]
    dropped_columns: list[str]
    masked_columns: list[str]
    rows_removed: int = 0
    checksums: dict[str, str] = Field(default_factory=dict)  # file -> sha256
    set_aside_columns: list[str] = Field(default_factory=list)  # sensitive: not trained on, kept for the fairness report
    maturity: MaturitySummary | None = None  # fraud projects: late labels and the embargo
    hashed_columns: list[str] = Field(default_factory=list)  # fraud: IDs replaced by salted hashes
    group_column: str | None = None  # the entity key of a group split


class FairnessGroup(BaseModel):
    group: str
    rows: int
    positives: int
    selected: int
    selection_rate: float  # selected / rows
    hit_rate: float | None  # positives among selected / selected; None when none selected
    base_rate: float  # positives / rows
    enough_rows: bool


class FairnessColumn(BaseModel):
    column: str
    trait: str
    groups: list[FairnessGroup]
    min_selection_ratio: float | None = None  # lowest group selection rate / highest, groups with enough rows
    note: str | None = None


class FairnessReport(BaseModel):
    model_version: int | None = None
    split: Literal["holdout"] = "holdout"
    rows: int
    selected: int
    rule: Literal["top_k", "fpr"]
    columns: list[FairnessColumn]


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
    gates: list["GateResult"] = Field(default_factory=list)  # fraud: the five promotion gates
    champion: bool = False  # fraud: the active version re-scored on this window


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


# ---------- Value model ----------

ParamSource = Literal["data", "user", "default"]


class ValueParam(BaseModel):
    key: str
    label: str
    value: float
    source: ParamSource
    unit: Literal["money", "rate", "count"]
    note: str = ""


class ValuePoint(BaseModel):
    """One operating point priced per month. Counts are scaled to rows_per_month."""

    name: Literal["contract", "optimal", "baseline"]
    threshold: float
    flagged_share: float
    fpr: float
    recall: float
    precision: float
    tp: float
    fp: float
    fn: float
    tn: float
    gross: float
    costs: float
    net: float
    net_low: float | None = None
    net_high: float | None = None
    recall_low: float | None = None
    recall_high: float | None = None


class CurvePoint(BaseModel):
    flagged_share: float
    recall: float
    fpr: float
    net: float


class Sensitivity(BaseModel):
    key: str
    label: str
    low_value: float
    low_net: float
    high_value: float
    high_net: float


class ValueReport(BaseModel):
    project_id: str
    solver: str
    baseline_solver: str | None = None
    eval_split: Literal["leaderboard", "holdout"]
    rows_eval: int
    params: list[ValueParam]
    contract: ValuePoint
    optimal: ValuePoint
    baseline: ValuePoint | None = None
    exposure_per_month: float
    uplift_net: float | None = None
    annual_net: float
    curve: list[CurvePoint]
    sensitivity: list[Sensitivity]
    breakeven: dict[str, float | None] = Field(default_factory=dict)
    assumptions: list[str] = Field(default_factory=list)
    headline: str
    formula: str


class ValueParamsIn(BaseModel):
    """User overrides. Null clears the override and the value falls back to data or the default."""

    rows_per_month: float | None = None
    value_per_positive: float | None = None
    action_success_rate: float | None = None
    cost_per_action: float | None = None
    cost_per_false_positive: float | None = None


# ---------- Intake ----------


class IntakeMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class IntakeRequest(BaseModel):
    message: str
    prefer_cache: bool = False  # replay a saved reply when one exists (the demo seed)


class IntakeResponse(BaseModel):
    message: str
    spec_patch: SpecPatch
    spec: ProblemSpec | None
    done: bool
    source: Literal["llm", "cache", "defaults"]
    history: list[IntakeMessage]


# ---------- Model versions, lists, health, plan ----------


class ModelVersionOut(BaseModel):
    id: str
    project_id: str
    version: int
    source: VersionSource
    solver_name: str  # internal; the UI shows it only in the technical drawer
    submission_id: str | None = None
    private_score: float
    public_score: float | None = None
    metric_name: str
    business_value: str  # headline line, computed in code
    improvement_line: str | None = None  # versus v1
    status: Literal["active", "retired"]
    created_at: datetime
    gates: list[GateResult] = Field(default_factory=list)
    stats: dict[str, Any] = Field(default_factory=dict)  # fraud: holdout queue numbers (per day, precision, false alarms)


class ListOut(BaseModel):
    id: str
    project_id: str
    name: str
    model_version: int
    model_version_id: str
    solver_name: str
    rows_scored: int
    top_n: int
    row_label: str
    action_label: str
    columns: list[str]
    preview: list[dict[str, Any]] = Field(default_factory=list)  # the top rows, rank first
    created_at: datetime
    download: str


class HealthOut(BaseModel):
    health: Health
    model_version: int
    rows: int
    positives: int
    score: float  # primary metric on the uploaded rows
    holdout_score: float  # the active version's private holdout score
    drop: float  # relative drop, positive means worse
    threshold: float
    metric_name: str
    line: str
    checked_at: datetime


class PlanOut(BaseModel):
    """Illustrative improvement plan shown on the Launch screen. The contest reward is for HANDOFF.md only."""

    subscription_per_month: float
    success_fee_share: float
    improvement_rel: float | None = None  # active vs v1, relative, on the private holdout
    value_uplift_per_month: float | None = None  # from the value model, active vs v1
    success_fee_per_month: float | None = None
    illustrative: bool = True
    lines: list[str] = Field(default_factory=list)


class ProjectSettingsIn(BaseModel):
    refresh_daily: bool | None = None
    min_improvement: float | None = None
    drift_threshold: float | None = None


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


# ---------- Fraud ----------

FRAUD_REQUIRED = ("transaction_id", "transaction_time", "amount", "customer_id", "is_fraud")
FRAUD_OPTIONAL = ("merchant_or_terminal_id", "currency", "label_time")


class FraudSettings(BaseModel):
    daily_capacity: int = Field(200, ge=1, le=100_000)  # cases the team reviews per day
    review_cost: float = Field(10.0, ge=0)  # cost of one review
    fraud_fee: float = Field(0.0, ge=0)  # cost of a missed fraud on top of its amount (chargeback fee)
    label_delay_days: int = Field(30, ge=1, le=180)  # how long until fraud is usually confirmed


class SchemaField(BaseModel):
    name: str
    required: bool
    column: str | None = None  # the user's column
    suggested: str | None = None


class SchemaOut(BaseModel):
    columns: list[str]
    fields: list[SchemaField]
    preview: list[dict[str, Any]] = Field(default_factory=list)
    confirmed: bool = False
    problems: list[str] = Field(default_factory=list)


class SchemaIn(BaseModel):
    mapping: dict[str, str | None]  # canonical name -> user column


class GateResult(BaseModel):
    key: Literal["hidden_data", "same_rows", "luck", "segments", "speed"]
    name: str
    passed: bool
    line: str  # plain words, numbers from code
    detail: dict[str, Any] = Field(default_factory=dict)


class QueueReason(BaseModel):
    text: str
    weight: float


class QueueCase(BaseModel):
    rank: int
    transaction_id: str
    time: str
    amount: float
    customer: str  # hashed
    risk: float
    expected_loss: float
    reasons: list[QueueReason]
    label: Literal["fraud", "not_fraud"] | None = None


class QueueOut(BaseModel):
    day: str
    model_version: int
    capacity: int
    rows_scored: int
    cases: list[QueueCase]
    expected_loss_total: float
    labeled: int
    created_at: datetime


class QueueLabelIn(BaseModel):
    label: Literal["fraud", "not_fraud"] | None


class WeekHealth(BaseModel):
    week_start: str
    week_end: str
    caught_per_day: float  # fraud money caught per day inside capacity
    fraud_per_day: float  # fraud money per day
    share: float  # caught / fraud money
    drop: float  # relative to the version's holdout share


class DriftFeature(BaseModel):
    name: str
    psi: float
    flagged: bool


class DriftOut(BaseModel):
    as_of: str
    model_version: int | None
    baseline_share: float | None
    weeks: list[WeekHealth]
    psi: list[DriftFeature]
    performance_drop: float | None  # latest mature week vs holdout, relative
    slipping: bool
    reason: Literal["performance", "drift", "both", "none"]
    line: str
    round_started: bool = False
    checked_at: datetime


class ClockIn(BaseModel):
    days: int = Field(28, ge=1, le=120)
    auto_round: bool = True


# ---------- Project ----------


class ProjectCreate(BaseModel):
    name: str | None = None
    template: Template = "fraud"
    sample: bool = True  # fraud: start from the sample transactions (False: the user uploads theirs)
    sample_file: str | None = None  # seed only: another file in the fraud template folder (the drift copy)
    salt: str | None = None  # seed only: a fixed ID salt so cached arena runs replay


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
    active_model: ModelVersionOut | None = None
    versions: list[ModelVersionOut] = Field(default_factory=list)
    current_result: str | None = None  # active version's business line
    improvement_line: str | None = None  # since v1
    result_short: str | None = None  # "Buyers reached: 34% to 52%" for tables
    health: Health = "unknown"
    health_check: HealthOut | None = None
    model_status: ModelStatus = "none"
    refresh_daily: bool = False
    min_improvement: float = 0.01
    drift_threshold: float = 0.10
    list_name: str = "Action list"
    updated_at: datetime | None = None
    fraud_settings: FraudSettings | None = None
    source: str = "sample"
    schema_confirmed: bool = False
    as_of: str | None = None
    can_jump: bool = False  # sample data beyond the as-of date exists
    drift: DriftOut | None = None
    money_per_day: float | None = None  # active version, fraud caught per day inside capacity
    net_per_day: float | None = None


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
    active_model_id: str | None = None
    min_improvement: float = 0.01
    drift_threshold: float = 0.10
    health: str = "unknown"
    health_json: str | None = None
    refresh_daily: bool = False
    fraud_settings_json: str | None = None
    mapping_json: str | None = None  # confirmed mapping, canonical -> user column
    as_of: str | None = None  # simulated today (ISO date)
    data_end: str | None = None  # last transaction date in the data
    salt: str | None = None
    source: str = "sample"  # sample or upload
    drift_json: str | None = None
    org_id: str | None = SQLField(default=None, index=True)
    created_at: datetime = SQLField(default_factory=_now)
    updated_at: datetime = SQLField(default_factory=_now)

    def fraud_settings(self) -> FraudSettings | None:
        return FraudSettings.model_validate_json(self.fraud_settings_json) if self.fraud_settings_json else None

    def drift(self) -> DriftOut | None:
        return DriftOut.model_validate_json(self.drift_json) if self.drift_json else None

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

    def health_check(self) -> HealthOut | None:
        return HealthOut.model_validate_json(self.health_json) if self.health_json else None

    def to_out(self, versions: list[ModelVersionOut] | None = None, *, running: bool = False) -> ProjectOut:
        versions = versions or []
        active = next((v for v in versions if v.id == self.active_model_id), None) or next((v for v in versions if v.status == "active"), None)
        v1 = next((v for v in versions if v.version == 1), None)
        from app.models_registry.promotion import list_framing, result_short  # noqa: PLC0415 - avoids an import cycle

        spec = self.spec()
        if self.health == "slipping":
            status = "slipping"
        elif active is None:
            status = "none"
        elif running or self.stage == "improve":
            status = "improving"
        else:
            status = "healthy"
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
            active_model=active,
            versions=versions,
            current_result=active.business_value if active else None,
            improvement_line=active.improvement_line if active else None,
            result_short=result_short(spec, v1, active) if spec and active else None,
            health=self.health,  # type: ignore[arg-type]
            health_check=self.health_check(),
            model_status=status,  # type: ignore[arg-type]
            refresh_daily=self.refresh_daily,
            min_improvement=self.min_improvement,
            drift_threshold=self.drift_threshold,
            list_name=list_framing(self.template, spec)["name"],
            updated_at=self.updated_at,
            fraud_settings=self.fraud_settings(),
            source=self.source or "sample",
            schema_confirmed=self.mapping_json is not None,
            as_of=self.as_of,
            can_jump=bool(self.as_of and self.data_end and self.as_of < self.data_end),
            drift=self.drift(),
            money_per_day=active.private_score if active and spec and spec.primary_metric == "fraud_amount_per_day" else None,
            net_per_day=(active.private_score - self.fraud_settings().daily_capacity * self.fraud_settings().review_cost)
            if active and spec and spec.primary_metric == "fraud_amount_per_day" and self.fraud_settings() else None,
        )


class ModelVersionRow(SQLModel, table=True):
    __tablename__ = "model_version"

    id: str = SQLField(default_factory=lambda: uuid.uuid4().hex[:12], primary_key=True)
    project_id: str = SQLField(index=True)
    version: int = 1
    source: str = "baseline"
    solver_name: str = ""
    submission_id: str | None = None
    private_score: float = 0.0
    public_score: float | None = None
    metric_name: str = ""
    business_value: str = ""
    status: str = "active"
    gates_json: str | None = None
    created_at: datetime = SQLField(default_factory=_now)


class CaseLabelRow(SQLModel, table=True):
    """An analyst's verdict on a queued case. Fed into the next improvement round with label_time = when given."""

    __tablename__ = "case_label"

    id: str = SQLField(default_factory=lambda: uuid.uuid4().hex[:12], primary_key=True)
    project_id: str = SQLField(index=True)
    transaction_id: str = SQLField(index=True)
    label: int = 1
    label_time: str = ""  # simulated now (the as-of date) when given
    model_version: int = 0
    created_at: datetime = SQLField(default_factory=_now)


class ListRow(SQLModel, table=True):
    __tablename__ = "scored_list"

    id: str = SQLField(default_factory=lambda: uuid.uuid4().hex[:12], primary_key=True)
    project_id: str = SQLField(index=True)
    model_version_id: str = ""
    model_version: int = 1
    solver_name: str = ""
    name: str = ""
    rows_scored: int = 0
    top_n: int = 0
    path: str = ""
    columns_json: str = "[]"
    created_at: datetime = SQLField(default_factory=_now)


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
    gates_json: str | None = None
    created_at: datetime = SQLField(default_factory=_now)


SubmissionOut.model_rebuild()
LeaderboardOut.model_rebuild()
