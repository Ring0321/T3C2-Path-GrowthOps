"""Deterministic multi-agent orchestration for one GrowthOps decision transaction."""

from __future__ import annotations

from pydantic import AwareDatetime, Field

from t3c2_path.agents.contracts import AgentCapability, AgentContract
from t3c2_path.algorithms.evidence_state import EvidenceStateEstimator
from t3c2_path.algorithms.path_twin import (
    LatentDimension,
    PathDefinition,
    PathSimulationResult,
    simulate_paths,
)
from t3c2_path.algorithms.safe_voi import (
    SafeVOIPolicy,
    TaskCandidate,
    TaskDecision,
    rank_tasks,
)
from t3c2_path.algorithms.safety_gate import (
    GatePolicy,
    GateResult,
    PublicationCandidate,
    evaluate_publication,
)
from t3c2_path.audit import AppendOnlyAuditStore, canonical_hash
from t3c2_path.domain import (
    AgentDecisionLog,
    ConsentRecord,
    DecisionPurpose,
    EvidenceRecord,
    FrozenModel,
    KnowledgeRule,
    ProfileSnapshot,
    PublicationAction,
    ReviewTicket,
)


class PriorState(FrozenModel):
    mean: float
    sd: float = Field(gt=0)
    half_life_days: float = Field(gt=0)


class GateMetrics(FrozenModel):
    expected_evidence_count: int = Field(gt=0)
    calibration_ece: float = Field(ge=0, le=1)
    fairness_gap: float = Field(ge=0, le=1)


class DecisionRequest(FrozenModel):
    decision_id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    purpose: DecisionPurpose
    decision_time: AwareDatetime
    consent: ConsentRecord
    evidence_records: tuple[EvidenceRecord, ...]
    priors: dict[str, PriorState] = Field(min_length=1)
    path_definitions: tuple[PathDefinition, ...]
    knowledge_rules: tuple[KnowledgeRule, ...]
    task_candidates: tuple[TaskCandidate, ...]
    gate_metrics: GateMetrics
    model_versions: dict[str, str] = Field(min_length=1)
    knowledge_version: str = Field(min_length=1)
    seed: int
    simulation_draws: int = Field(ge=100, le=100_000)
    is_synthetic: bool


class DecisionPackage(FrozenModel):
    decision_id: str
    subject_id: str
    action: PublicationAction
    reason_codes: tuple[str, ...] = Field(min_length=1)
    profiles: tuple[ProfileSnapshot, ...]
    paths: tuple[PathSimulationResult, ...]
    tasks: tuple[TaskDecision, ...]
    gate: GateResult
    explanation: str = Field(min_length=1)
    audit_log: AgentDecisionLog
    review_ticket: ReviewTicket | None


class GrowthOpsOrchestrator:
    def __init__(self, audit_store: AppendOnlyAuditStore) -> None:
        self.audit_store = audit_store
        self.contracts = {
            "evidence": AgentContract.evidence_agent(),
            "path": AgentContract.path_agent(),
            "task": AgentContract.task_agent(),
            "governance": AgentContract.governance_agent(),
            "explanation": AgentContract.explanation_agent(),
            "audit": AgentContract.audit_agent(),
        }

    def evaluate(self, request: DecisionRequest) -> DecisionPackage:
        self._validate_subject_scope(request)
        input_hash = canonical_hash(request.model_dump(mode="json"))
        consent_valid = request.consent.allows(request.purpose, request.decision_time)
        if not consent_valid:
            gate = evaluate_publication(
                PublicationCandidate(
                    candidate_id=request.decision_id,
                    purpose=request.purpose,
                    consent_valid=False,
                    evidence_coverage=0.0,
                    rules_valid=False,
                    calibration_ece=request.gate_metrics.calibration_ece,
                    fairness_gap=request.gate_metrics.fairness_gap,
                    uncertainty_width=0.0,
                    student_workload_hours=0.0,
                    is_high_stakes=request.purpose is DecisionPurpose.HIGH_STAKES,
                ),
                GatePolicy(),
            )
            return self._finalize(
                request=request,
                input_hash=input_hash,
                profiles=(),
                paths=(),
                tasks=(),
                gate=gate,
            )

        profiles = self._build_profiles(request)
        paths = self._build_paths(request, profiles)
        tasks = self._build_tasks(request)
        gate = self._gate(request, profiles, paths, tasks)
        return self._finalize(
            request=request,
            input_hash=input_hash,
            profiles=profiles,
            paths=paths,
            tasks=tasks,
            gate=gate,
        )

    def _validate_subject_scope(self, request: DecisionRequest) -> None:
        if request.consent.subject_id != request.subject_id:
            raise ValueError("consent subject mismatch")
        for record in request.evidence_records:
            if record.subject_id != request.subject_id:
                raise ValueError(f"evidence subject mismatch: {record.evidence_id}")
            if record.authorization_id != request.consent.consent_id:
                raise ValueError(f"evidence authorization mismatch: {record.evidence_id}")

    def _build_profiles(self, request: DecisionRequest) -> tuple[ProfileSnapshot, ...]:
        contract = self.contracts["evidence"]
        contract.require(AgentCapability.READ_EVIDENCE)
        contract.require(AgentCapability.WRITE_PROFILE)
        profiles: list[ProfileSnapshot] = []
        for dimension, prior in sorted(request.priors.items()):
            records = tuple(
                item for item in request.evidence_records if item.dimension == dimension
            )
            state = EvidenceStateEstimator(
                request.decision_time, prior.half_life_days
            ).update(prior.mean, prior.sd, records)
            if not state.used_evidence_ids:
                continue
            profiles.append(
                ProfileSnapshot(
                    snapshot_id=f"{request.decision_id}:profile:{dimension}",
                    subject_id=request.subject_id,
                    dimension=dimension,
                    posterior_mean=state.posterior_mean,
                    posterior_sd=state.posterior_sd,
                    interval_low=state.interval_low,
                    interval_high=state.interval_high,
                    evidence_ids=state.used_evidence_ids,
                    context="context-preserving evidence update",
                    model_version=request.model_versions["evidence"],
                    created_at=request.decision_time,
                    is_synthetic=request.is_synthetic,
                )
            )
        return tuple(profiles)

    def _build_paths(
        self, request: DecisionRequest, profiles: tuple[ProfileSnapshot, ...]
    ) -> tuple[PathSimulationResult, ...]:
        contract = self.contracts["path"]
        contract.require(AgentCapability.READ_RULE)
        contract.require(AgentCapability.WRITE_PATH)
        states = {
            item.dimension: LatentDimension(mean=item.posterior_mean, sd=item.posterior_sd)
            for item in profiles
        }
        if not request.path_definitions:
            return ()
        return simulate_paths(
            states,
            request.path_definitions,
            request.knowledge_rules,
            request.decision_time,
            draws=request.simulation_draws,
            seed=request.seed,
        )

    def _build_tasks(self, request: DecisionRequest) -> tuple[TaskDecision, ...]:
        contract = self.contracts["task"]
        contract.require(AgentCapability.READ_RULE)
        contract.require(AgentCapability.WRITE_TASK)
        return rank_tasks(request.task_candidates, SafeVOIPolicy())

    def _gate(
        self,
        request: DecisionRequest,
        profiles: tuple[ProfileSnapshot, ...],
        paths: tuple[PathSimulationResult, ...],
        tasks: tuple[TaskDecision, ...],
    ) -> GateResult:
        contract = self.contracts["governance"]
        contract.require(AgentCapability.READ_RULE)
        contract.require(AgentCapability.WRITE_GATE)
        used_evidence = {evidence_id for item in profiles for evidence_id in item.evidence_ids}
        coverage = min(
            1.0, len(used_evidence) / request.gate_metrics.expected_evidence_count
        )
        rules_valid = all(not item.invalid_rule_ids for item in paths)
        uncertainty_width = max(
            (item.interval_high - item.interval_low for item in profiles), default=0.0
        )
        first_passed = next((item for item in tasks if item.gate == "PASS"), None)
        workload = 0.0
        if first_passed is not None:
            workload = next(
                item.estimated_hours
                for item in request.task_candidates
                if item.task_id == first_passed.task_id
            )
        return evaluate_publication(
            PublicationCandidate(
                candidate_id=request.decision_id,
                purpose=request.purpose,
                consent_valid=True,
                evidence_coverage=coverage,
                rules_valid=rules_valid,
                calibration_ece=request.gate_metrics.calibration_ece,
                fairness_gap=request.gate_metrics.fairness_gap,
                uncertainty_width=uncertainty_width,
                student_workload_hours=workload,
                is_high_stakes=request.purpose is DecisionPurpose.HIGH_STAKES,
            ),
            GatePolicy(),
        )

    def _finalize(
        self,
        *,
        request: DecisionRequest,
        input_hash: str,
        profiles: tuple[ProfileSnapshot, ...],
        paths: tuple[PathSimulationResult, ...],
        tasks: tuple[TaskDecision, ...],
        gate: GateResult,
    ) -> DecisionPackage:
        self.contracts["explanation"].require(AgentCapability.WRITE_EXPLANATION)
        explanation = self._explain(gate, paths, tasks)
        review_ticket = None
        if gate.action is PublicationAction.HUMAN_REVIEW:
            review_ticket = ReviewTicket(
                ticket_id=f"{request.decision_id}:review",
                decision_id=request.decision_id,
                queue="qualified-career-counsellor",
                priority="HIGH",
                reason_codes=gate.reason_codes,
                created_at=request.decision_time,
                is_synthetic=request.is_synthetic,
            )
        evidence_ids = tuple(
            sorted({evidence_id for item in profiles for evidence_id in item.evidence_ids})
        )
        audit_log = AgentDecisionLog(
            decision_id=request.decision_id,
            subject_id=request.subject_id,
            purpose=request.purpose,
            input_hash=input_hash,
            evidence_ids=evidence_ids,
            model_versions=tuple(sorted(request.model_versions.values())),
            knowledge_versions=(request.knowledge_version,),
            action=gate.action,
            reason_codes=gate.reason_codes,
            created_at=request.decision_time,
            is_synthetic=request.is_synthetic,
        )
        self.contracts["audit"].require(AgentCapability.WRITE_AUDIT)
        self.audit_store.append(
            request.decision_id,
            audit_log.model_dump(mode="json"),
            created_at=request.decision_time,
        )
        return DecisionPackage(
            decision_id=request.decision_id,
            subject_id=request.subject_id,
            action=gate.action,
            reason_codes=gate.reason_codes,
            profiles=profiles,
            paths=paths,
            tasks=tasks,
            gate=gate,
            explanation=explanation,
            audit_log=audit_log,
            review_ticket=review_ticket,
        )

    @staticmethod
    def _explain(
        gate: GateResult,
        paths: tuple[PathSimulationResult, ...],
        tasks: tuple[TaskDecision, ...],
    ) -> str:
        path_count = sum(item.pareto_front for item in paths)
        next_task = next((item.task_id for item in tasks if item.gate == "PASS"), "none")
        return (
            f"Decision action: {gate.action.value}. The current evidence retains "
            f"{path_count} non-dominated path(s); next reversible task: {next_task}. "
            "Intervals represent uncertainty, and this formative output is not an "
            "admission probability, student ranking, or service-effect claim. "
            f"Reason codes: {', '.join(gate.reason_codes)}."
        )


__all__ = [
    "DecisionPackage",
    "DecisionRequest",
    "GateMetrics",
    "GrowthOpsOrchestrator",
    "PriorState",
]
