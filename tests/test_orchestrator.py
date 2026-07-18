from datetime import UTC, datetime, timedelta

import pytest

from t3c2_path.algorithms.path_twin import PathDefinition
from t3c2_path.algorithms.safe_voi import TaskCandidate
from t3c2_path.application import (
    DecisionRequest,
    GateMetrics,
    GrowthOpsOrchestrator,
    PriorState,
)
from t3c2_path.audit import AppendOnlyAuditStore
from t3c2_path.domain import (
    ConsentRecord,
    DecisionPurpose,
    EvidenceRecord,
    EvidenceStatus,
    PublicationAction,
    SourceKind,
)


NOW = datetime(2026, 7, 19, 8, 0, tzinfo=UTC)


def consent(*, purpose: DecisionPurpose = DecisionPurpose.FORMATIVE_PLANNING) -> ConsentRecord:
    return ConsentRecord(
        consent_id="consent-001",
        subject_id="synthetic-student-001",
        purposes=frozenset({purpose}),
        valid_from=NOW - timedelta(days=1),
        valid_to=NOW + timedelta(days=30),
        is_synthetic=True,
    )


def evidence(evidence_id: str, dimension: str, value: float) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=evidence_id,
        subject_id="synthetic-student-001",
        dimension=dimension,
        observed_value=value,
        base_sd=6.0,
        reliability=0.9,
        observed_at=NOW - timedelta(days=2),
        recorded_at=NOW,
        source_kind=SourceKind.WORK_SAMPLE,
        context="structured_task",
        authorization_id="consent-001",
        status=EvidenceStatus.ACTIVE,
        is_synthetic=True,
    )


def request(**overrides: object) -> DecisionRequest:
    data: dict[str, object] = {
        "decision_id": "decision-synthetic-001",
        "subject_id": "synthetic-student-001",
        "purpose": DecisionPurpose.FORMATIVE_PLANNING,
        "decision_time": NOW,
        "consent": consent(),
        "evidence_records": (
            evidence("e-analysis", "analysis", 65),
            evidence("e-communication", "communication", 63),
        ),
        "priors": {
            "analysis": PriorState(mean=50, sd=10, half_life_days=56),
            "communication": PriorState(mean=50, sd=10, half_life_days=56),
        },
        "path_definitions": (
            PathDefinition(
                path_id="market-employment",
                requirements={"analysis": 60.0, "communication": 60.0},
                weights={"analysis": 0.5, "communication": 0.5},
                weekly_workload_hours=10,
                transferability=85,
                window_days=90,
                critical_margin=15,
            ),
        ),
        "knowledge_rules": (),
        "task_candidates": (
            TaskCandidate(
                task_id="portfolio-experiment",
                expected_growth=8,
                information_gain=8,
                transferability=9,
                window_rescue=6,
                burden=3,
                risk=1,
                estimated_hours=2,
                monetary_cost=0,
                consent_valid=True,
                rules_valid=True,
                is_reversible=True,
                is_high_stakes=False,
                is_paid_service=False,
            ),
        ),
        "gate_metrics": GateMetrics(
            expected_evidence_count=2,
            calibration_ece=0.04,
            fairness_gap=0.05,
        ),
        "model_versions": {
            "evidence": "evidence-state/0.1.0",
            "path": "path-twin/0.1.0",
            "task": "safe-voi/0.1.0",
            "gate": "safety-gate/0.1.0",
        },
        "knowledge_version": "synthetic-rules/0.1.0",
        "seed": 7,
        "simulation_draws": 300,
        "is_synthetic": True,
    }
    data.update(overrides)
    return DecisionRequest(**data)


def test_end_to_end_decision_is_reproducible_and_auditable() -> None:
    first_store = AppendOnlyAuditStore()
    second_store = AppendOnlyAuditStore()
    first = GrowthOpsOrchestrator(first_store).evaluate(request())
    second = GrowthOpsOrchestrator(second_store).evaluate(request())
    assert first == second
    assert first.action is PublicationAction.PUBLISH
    assert first.profiles[0].evidence_ids
    assert first.paths[0].path_id == "market-employment"
    assert first.tasks[0].task_id == "portfolio-experiment"
    assert AppendOnlyAuditStore.verify(first_store.events())


def test_orchestrator_rejects_cross_subject_evidence() -> None:
    foreign = evidence("foreign", "analysis", 90).model_copy(
        update={"subject_id": "another-student"}
    )
    with pytest.raises(ValueError, match="subject mismatch"):
        GrowthOpsOrchestrator(AppendOnlyAuditStore()).evaluate(
            request(evidence_records=(foreign,))
        )


def test_invalid_consent_blocks_without_running_a_soft_override() -> None:
    invalid = consent().model_copy(update={"withdrawn_at": NOW - timedelta(minutes=1)})
    result = GrowthOpsOrchestrator(AppendOnlyAuditStore()).evaluate(request(consent=invalid))
    assert result.action is PublicationAction.BLOCK
    assert "CONSENT_INVALID" in result.reason_codes
    assert not result.paths
    assert not result.tasks


def test_high_stakes_request_creates_a_human_review_ticket() -> None:
    high_stakes_consent = consent(purpose=DecisionPurpose.HIGH_STAKES)
    result = GrowthOpsOrchestrator(AppendOnlyAuditStore()).evaluate(
        request(
            purpose=DecisionPurpose.HIGH_STAKES,
            consent=high_stakes_consent,
        )
    )
    assert result.action is PublicationAction.HUMAN_REVIEW
    assert result.review_ticket is not None
    assert "HIGH_STAKES_REQUIRES_HUMAN" in result.review_ticket.reason_codes


def test_explanation_preserves_uncertainty_and_avoids_service_causal_language() -> None:
    result = GrowthOpsOrchestrator(AppendOnlyAuditStore()).evaluate(request())
    assert "uncertainty" in result.explanation.lower()
    assert "caused" not in result.explanation.lower()
    assert "导致" not in result.explanation
