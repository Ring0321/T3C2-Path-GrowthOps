"""Immutable domain contracts for evidence-aware growth decisions.

The models deliberately keep facts, inferences, paths, tasks and causal reports
separate.  They are boundary objects: external data is rejected unless it
matches the declared schema, while internal algorithms can rely on the types.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

Identifier = Annotated[str, Field(min_length=1, max_length=160)]
NonEmptyText = Annotated[str, Field(min_length=1, max_length=4_000)]
Probability = Annotated[float, Field(ge=0.0, le=1.0)]
PositiveProbability = Annotated[float, Field(gt=0.0, le=1.0)]
HashDigest = Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]


class SourceKind(StrEnum):
    SELF_REPORT = "SELF_REPORT"
    WORK_SAMPLE = "WORK_SAMPLE"
    RUBRIC = "RUBRIC"
    SYSTEM_EVENT = "SYSTEM_EVENT"
    EXTERNAL_RULE = "EXTERNAL_RULE"
    AI_DRAFT = "AI_DRAFT"


class EvidenceStatus(StrEnum):
    ACTIVE = "ACTIVE"
    DISPUTED = "DISPUTED"
    WITHDRAWN = "WITHDRAWN"
    SUPERSEDED = "SUPERSEDED"


class DecisionPurpose(StrEnum):
    FORMATIVE_PLANNING = "FORMATIVE_PLANNING"
    RESEARCH_EVALUATION = "RESEARCH_EVALUATION"
    SERVICE_EVALUATION = "SERVICE_EVALUATION"
    HIGH_STAKES = "HIGH_STAKES"


class ClaimLevel(StrEnum):
    DESCRIPTIVE = "DESCRIPTIVE"
    ASSOCIATIONAL = "ASSOCIATIONAL"
    FORMATIVE = "FORMATIVE"
    CAUSAL_GROUP = "CAUSAL_GROUP"
    SYNTHETIC_ONLY = "SYNTHETIC_ONLY"


class PathStatus(StrEnum):
    FEASIBLE = "FEASIBLE"
    NEEDS_VERIFICATION = "NEEDS_VERIFICATION"
    BLOCKED = "BLOCKED"
    ARCHIVED = "ARCHIVED"


class PublicationAction(StrEnum):
    PUBLISH = "PUBLISH"
    QUALIFIED = "QUALIFIED"
    DEFER = "DEFER"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    BLOCK = "BLOCK"


class FrozenModel(BaseModel):
    """Base class for append-only records and versioned outputs."""

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)


class ConsentRecord(FrozenModel):
    consent_id: Identifier
    subject_id: Identifier
    purposes: frozenset[DecisionPurpose] = Field(min_length=1)
    valid_from: AwareDatetime
    valid_to: AwareDatetime
    withdrawn_at: AwareDatetime | None = None
    is_synthetic: bool = False

    @model_validator(mode="after")
    def validate_window(self) -> ConsentRecord:
        if self.valid_to <= self.valid_from:
            raise ValueError("valid_to must be after valid_from")
        if self.withdrawn_at is not None and self.withdrawn_at < self.valid_from:
            raise ValueError("withdrawn_at cannot precede valid_from")
        return self

    def allows(self, purpose: DecisionPurpose, at: datetime) -> bool:
        """Return whether the consent authorizes a new decision at ``at``."""

        if at.tzinfo is None:
            raise ValueError("at must be timezone-aware")
        within_window = self.valid_from <= at <= self.valid_to
        not_withdrawn = self.withdrawn_at is None or at < self.withdrawn_at
        return purpose in self.purposes and within_window and not_withdrawn


class EvidenceRecord(FrozenModel):
    evidence_id: Identifier
    subject_id: Identifier
    dimension: Identifier
    observed_value: Annotated[float, Field(ge=0.0, le=100.0)] | None
    base_sd: Annotated[float, Field(gt=0.0)]
    reliability: PositiveProbability
    observed_at: AwareDatetime
    recorded_at: AwareDatetime
    source_kind: SourceKind
    context: NonEmptyText
    authorization_id: Identifier
    status: EvidenceStatus
    duplicate_group: Identifier | None = None
    source_reference: str | None = Field(default=None, max_length=2_000)
    is_synthetic: bool = False

    @model_validator(mode="after")
    def validate_timestamps(self) -> EvidenceRecord:
        if self.recorded_at < self.observed_at:
            raise ValueError("recorded_at cannot precede observed_at")
        return self


class ProfileSnapshot(FrozenModel):
    snapshot_id: Identifier
    subject_id: Identifier
    dimension: Identifier
    posterior_mean: float
    posterior_sd: Annotated[float, Field(gt=0.0)]
    interval_low: float
    interval_high: float
    evidence_ids: tuple[Identifier, ...] = Field(min_length=1)
    context: NonEmptyText
    model_version: Identifier
    created_at: AwareDatetime
    is_synthetic: bool = False

    @model_validator(mode="after")
    def validate_interval(self) -> ProfileSnapshot:
        if not self.interval_low <= self.posterior_mean <= self.interval_high:
            raise ValueError("posterior_mean must lie inside the interval")
        return self


class KnowledgeRule(FrozenModel):
    rule_id: Identifier
    track_id: Identifier
    rule_type: Identifier
    expression: NonEmptyText
    source_url: NonEmptyText
    source_version: Identifier
    valid_from: AwareDatetime
    valid_to: AwareDatetime
    retrieved_at: AwareDatetime
    is_synthetic: bool = False

    @model_validator(mode="after")
    def validate_window(self) -> KnowledgeRule:
        if self.valid_to <= self.valid_from:
            raise ValueError("rule valid_to must be after valid_from")
        return self

    def is_valid_at(self, at: datetime) -> bool:
        if at.tzinfo is None:
            raise ValueError("at must be timezone-aware")
        return self.valid_from <= at <= self.valid_to


class PathNode(FrozenModel):
    node_id: Identifier
    title: NonEmptyText
    due_at: AwareDatetime
    hard_rule_ids: tuple[Identifier, ...] = ()
    readiness_dimensions: tuple[Identifier, ...] = Field(min_length=1)
    is_reversible: bool


class PathPlan(FrozenModel):
    plan_id: Identifier
    subject_id: Identifier
    track_id: Identifier
    status: PathStatus
    readiness_mean: Annotated[float, Field(ge=0.0, le=100.0)]
    interval_low: Annotated[float, Field(ge=0.0, le=100.0)]
    interval_high: Annotated[float, Field(ge=0.0, le=100.0)]
    feasible_probability: Probability | None
    nodes: tuple[PathNode, ...] = Field(min_length=1)
    backup_track_ids: tuple[Identifier, ...] = ()
    knowledge_version: Identifier
    generated_at: AwareDatetime
    is_synthetic: bool = False

    @model_validator(mode="after")
    def validate_readiness(self) -> PathPlan:
        if not self.interval_low <= self.readiness_mean <= self.interval_high:
            raise ValueError("readiness_mean must lie inside the interval")
        if self.status is PathStatus.NEEDS_VERIFICATION and self.feasible_probability is not None:
            raise ValueError("unverified hard rules cannot produce a feasibility probability")
        return self


class TaskCard(FrozenModel):
    task_id: Identifier
    subject_id: Identifier
    title: NonEmptyText
    target_uncertainty: NonEmptyText
    completion_criteria: NonEmptyText
    evidence_requirement: NonEmptyText
    exit_condition: NonEmptyText
    estimated_hours: Annotated[float, Field(ge=0.0, le=500.0)]
    monetary_cost: Annotated[float, Field(ge=0.0)]
    is_reversible: bool
    is_high_stakes: bool
    knowledge_rule_ids: tuple[Identifier, ...] = ()
    created_at: AwareDatetime
    is_synthetic: bool = False


class ServiceExposure(FrozenModel):
    exposure_id: Identifier
    subject_id: Identifier
    service_id: Identifier
    strategy_version: Identifier
    assigned: bool
    started_at: AwareDatetime
    ended_at: AwareDatetime | None
    dose: Annotated[float, Field(ge=0.0)]
    recorded_at: AwareDatetime
    is_synthetic: bool = False

    @model_validator(mode="after")
    def validate_window(self) -> ServiceExposure:
        if self.ended_at is not None and self.ended_at < self.started_at:
            raise ValueError("ended_at cannot precede started_at")
        return self


class StudentValueAddedReport(FrozenModel):
    report_id: Identifier
    subject_id: Identifier
    observed_readiness: float
    expected_readiness: float
    estimate: float
    interval_low: float
    interval_high: float
    reference_definition: NonEmptyText
    model_version: Identifier
    claim_level: ClaimLevel
    created_at: AwareDatetime
    is_synthetic: bool = False

    @model_validator(mode="after")
    def validate_claim(self) -> StudentValueAddedReport:
        if self.claim_level not in {ClaimLevel.FORMATIVE, ClaimLevel.SYNTHETIC_ONLY}:
            raise ValueError("student VA is limited to formative or synthetic claims")
        if not self.interval_low <= self.estimate <= self.interval_high:
            raise ValueError("estimate must lie inside the interval")
        return self


class ServiceEffectReport(FrozenModel):
    report_id: Identifier
    population_definition: NonEmptyText
    strategy_version: Identifier
    estimand: Identifier
    estimate: float
    interval_low: float
    interval_high: float
    overlap_min: Probability
    overlap_max: Probability
    claim_level: ClaimLevel
    created_at: AwareDatetime
    is_synthetic: bool = False

    @model_validator(mode="after")
    def validate_effect(self) -> ServiceEffectReport:
        if not self.interval_low <= self.estimate <= self.interval_high:
            raise ValueError("estimate must lie inside the interval")
        if self.overlap_min > self.overlap_max:
            raise ValueError("overlap_min cannot exceed overlap_max")
        if self.claim_level is ClaimLevel.FORMATIVE:
            raise ValueError("service effect cannot use the individual formative claim level")
        return self


# Backward-compatible name from the research data dictionary. It is deliberately
# an alias for student VA only; service effects use ServiceEffectReport.
ValueAddedReport = StudentValueAddedReport


class AgentDecisionLog(FrozenModel):
    decision_id: Identifier
    subject_id: Identifier
    purpose: DecisionPurpose
    input_hash: HashDigest
    evidence_ids: tuple[Identifier, ...]
    model_versions: tuple[Identifier, ...] = Field(min_length=1)
    knowledge_versions: tuple[Identifier, ...]
    action: PublicationAction
    reason_codes: tuple[Identifier, ...] = Field(min_length=1)
    created_at: AwareDatetime
    is_synthetic: bool = False


class ReviewTicket(FrozenModel):
    ticket_id: Identifier
    decision_id: Identifier
    queue: Identifier
    priority: Annotated[str, Field(pattern=r"^(LOW|MEDIUM|HIGH|CRITICAL)$")]
    reason_codes: tuple[Identifier, ...] = Field(min_length=1)
    created_at: AwareDatetime
    is_synthetic: bool = False


class HumanOverrideRecord(FrozenModel):
    override_id: Identifier
    decision_id: Identifier
    reviewer_id: Identifier
    original_action: PublicationAction
    override_action: PublicationAction
    reason_codes: tuple[Identifier, ...] = Field(min_length=1)
    occurred_at: AwareDatetime
    is_synthetic: bool = False


class DisputeRecord(FrozenModel):
    dispute_id: Identifier
    subject_id: Identifier
    evidence_id: Identifier
    requested_action: Annotated[str, Field(pattern=r"^(CORRECT|WITHDRAW|RESTRICT)$")]
    statement: NonEmptyText
    status: Annotated[str, Field(pattern=r"^(OPEN|UPHELD|REJECTED|RESOLVED)$")]
    created_at: AwareDatetime
    is_synthetic: bool = False


class EventEnvelope(FrozenModel):
    event_id: Identifier
    aggregate_type: Identifier
    aggregate_id: Identifier
    event_type: Identifier
    occurred_at: AwareDatetime
    payload_hash: HashDigest
    schema_version: Identifier
    is_synthetic: bool = False


__all__ = [
    "AgentDecisionLog",
    "ClaimLevel",
    "ConsentRecord",
    "DecisionPurpose",
    "DisputeRecord",
    "EventEnvelope",
    "EvidenceRecord",
    "EvidenceStatus",
    "HumanOverrideRecord",
    "KnowledgeRule",
    "PathNode",
    "PathPlan",
    "PathStatus",
    "ProfileSnapshot",
    "PublicationAction",
    "ReviewTicket",
    "ServiceEffectReport",
    "ServiceExposure",
    "SourceKind",
    "StudentValueAddedReport",
    "TaskCard",
    "ValueAddedReport",
]
