from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from t3c2_path.domain import (
    AgentDecisionLog,
    ClaimLevel,
    ConsentRecord,
    DecisionPurpose,
    DisputeRecord,
    EvidenceRecord,
    EvidenceStatus,
    EventEnvelope,
    KnowledgeRule,
    PathNode,
    PathPlan,
    PathStatus,
    ProfileSnapshot,
    PublicationAction,
    ReviewTicket,
    ServiceEffectReport,
    ServiceExposure,
    SourceKind,
    StudentValueAddedReport,
    TaskCard,
)


NOW = datetime(2026, 7, 19, 8, 0, tzinfo=UTC)


def valid_consent(**overrides: object) -> ConsentRecord:
    data: dict[str, object] = {
        "consent_id": "consent-001",
        "subject_id": "synthetic-student-001",
        "purposes": frozenset({DecisionPurpose.FORMATIVE_PLANNING}),
        "valid_from": NOW - timedelta(days=1),
        "valid_to": NOW + timedelta(days=30),
        "is_synthetic": True,
    }
    data.update(overrides)
    return ConsentRecord(**data)


def valid_evidence(**overrides: object) -> EvidenceRecord:
    data: dict[str, object] = {
        "evidence_id": "evidence-001",
        "subject_id": "synthetic-student-001",
        "dimension": "communication",
        "observed_value": 62.0,
        "base_sd": 8.0,
        "reliability": 0.8,
        "observed_at": NOW - timedelta(days=5),
        "recorded_at": NOW,
        "source_kind": SourceKind.WORK_SAMPLE,
        "context": "structured_interview",
        "authorization_id": "consent-001",
        "status": EvidenceStatus.ACTIVE,
        "is_synthetic": True,
    }
    data.update(overrides)
    return EvidenceRecord(**data)


def test_unknown_evidence_value_is_preserved_instead_of_becoming_zero() -> None:
    evidence = valid_evidence(observed_value=None)
    assert evidence.observed_value is None


def test_external_models_forbid_unexpected_fields() -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        valid_evidence(unverified_label="introvert")


def test_domain_records_are_immutable_versions() -> None:
    evidence = valid_evidence()
    with pytest.raises(ValidationError, match="frozen"):
        evidence.observed_value = 90.0  # type: ignore[misc]


@pytest.mark.parametrize(
    ("at", "purpose", "expected"),
    [
        (NOW, DecisionPurpose.FORMATIVE_PLANNING, True),
        (NOW, DecisionPurpose.SERVICE_EVALUATION, False),
        (NOW + timedelta(days=31), DecisionPurpose.FORMATIVE_PLANNING, False),
    ],
)
def test_consent_is_bound_to_purpose_and_time(
    at: datetime, purpose: DecisionPurpose, expected: bool
) -> None:
    assert valid_consent().allows(purpose=purpose, at=at) is expected


def test_withdrawn_consent_cannot_authorize_new_decisions() -> None:
    consent = valid_consent(withdrawn_at=NOW - timedelta(minutes=1))
    assert not consent.allows(DecisionPurpose.FORMATIVE_PLANNING, NOW)


@pytest.mark.parametrize("reliability", [-0.1, 0.0, 1.1])
def test_evidence_reliability_is_a_probability(reliability: float) -> None:
    with pytest.raises(ValidationError):
        valid_evidence(reliability=reliability)


def test_profile_snapshot_must_reference_evidence_and_contain_mean() -> None:
    snapshot = ProfileSnapshot(
        snapshot_id="snapshot-001",
        subject_id="synthetic-student-001",
        dimension="communication",
        posterior_mean=61.5,
        posterior_sd=4.5,
        interval_low=52.7,
        interval_high=70.3,
        evidence_ids=("evidence-001",),
        context="structured_interview",
        model_version="evidence-state/0.1.0",
        created_at=NOW,
        is_synthetic=True,
    )
    assert snapshot.interval_low <= snapshot.posterior_mean <= snapshot.interval_high

    with pytest.raises(ValidationError):
        ProfileSnapshot(
            **{
                **snapshot.model_dump(),
                "snapshot_id": "snapshot-invalid",
                "evidence_ids": (),
            }
        )


def test_knowledge_rule_requires_a_validity_window_and_source() -> None:
    with pytest.raises(ValidationError):
        KnowledgeRule(
            rule_id="rule-001",
            track_id="civil-service",
            rule_type="hard_eligibility",
            expression="region == allowed_region",
            source_url="https://example.invalid/rule",
            source_version="2026-v1",
            valid_from=NOW,
            valid_to=NOW - timedelta(days=1),
            retrieved_at=NOW,
            is_synthetic=True,
        )


def test_va_and_se_are_different_types_with_different_claim_boundaries() -> None:
    va = StudentValueAddedReport(
        report_id="va-001",
        subject_id="synthetic-student-001",
        observed_readiness=65.0,
        expected_readiness=60.0,
        estimate=5.0,
        interval_low=1.0,
        interval_high=9.0,
        reference_definition="same stage and baseline band",
        model_version="va/0.1.0",
        claim_level=ClaimLevel.FORMATIVE,
        created_at=NOW,
        is_synthetic=True,
    )
    se = ServiceEffectReport(
        report_id="se-001",
        population_definition="synthetic wait-list cohort",
        strategy_version="service/0.1.0",
        estimand="ITT_ATE",
        estimate=3.0,
        interval_low=0.5,
        interval_high=5.5,
        overlap_min=0.2,
        overlap_max=0.8,
        claim_level=ClaimLevel.SYNTHETIC_ONLY,
        created_at=NOW,
        is_synthetic=True,
    )
    assert va.subject_id is not None
    assert not hasattr(se, "subject_id")
    assert va.claim_level is ClaimLevel.FORMATIVE
    assert se.claim_level is ClaimLevel.SYNTHETIC_ONLY


def test_service_exposure_keeps_assignment_separate_from_actual_dose() -> None:
    exposure = ServiceExposure(
        exposure_id="exposure-001",
        subject_id="synthetic-student-001",
        service_id="wait-list-pilot",
        strategy_version="service/0.1.0",
        assigned=True,
        started_at=NOW,
        ended_at=None,
        dose=0.0,
        recorded_at=NOW,
        is_synthetic=True,
    )
    assert exposure.assigned is True
    assert exposure.dose == 0.0


def test_task_card_has_exit_and_evidence_contracts() -> None:
    task = TaskCard(
        task_id="task-001",
        subject_id="synthetic-student-001",
        title="Conduct one informational interview",
        target_uncertainty="market-role fit",
        completion_criteria="one interview note with three counterexamples",
        evidence_requirement="signed self-reflection and anonymized note",
        exit_condition="student withdraws or reports distress",
        estimated_hours=1.0,
        monetary_cost=0.0,
        is_reversible=True,
        is_high_stakes=False,
        knowledge_rule_ids=(),
        created_at=NOW,
        is_synthetic=True,
    )
    assert task.is_reversible
    assert task.exit_condition


def test_path_plan_keeps_hard_rules_and_backup_tracks_explicit() -> None:
    node = PathNode(
        node_id="node-001",
        title="Verify application eligibility",
        due_at=NOW + timedelta(days=7),
        hard_rule_ids=("rule-001",),
        readiness_dimensions=("eligibility",),
        is_reversible=True,
    )
    plan = PathPlan(
        plan_id="plan-001",
        subject_id="synthetic-student-001",
        track_id="civil-service",
        status=PathStatus.NEEDS_VERIFICATION,
        readiness_mean=58.0,
        interval_low=45.0,
        interval_high=71.0,
        feasible_probability=None,
        nodes=(node,),
        backup_track_ids=("market-employment",),
        knowledge_version="rules/2026-v1",
        generated_at=NOW,
        is_synthetic=True,
    )
    assert plan.status is PathStatus.NEEDS_VERIFICATION
    assert plan.feasible_probability is None
    assert plan.nodes[0].hard_rule_ids == ("rule-001",)


def test_disputes_and_events_are_append_only_references() -> None:
    dispute = DisputeRecord(
        dispute_id="dispute-001",
        subject_id="synthetic-student-001",
        evidence_id="evidence-001",
        requested_action="WITHDRAW",
        statement="The evidence was collected for another purpose.",
        status="OPEN",
        created_at=NOW,
        is_synthetic=True,
    )
    event = EventEnvelope(
        event_id="event-001",
        aggregate_type="EvidenceRecord",
        aggregate_id=dispute.evidence_id,
        event_type="EVIDENCE_DISPUTED",
        occurred_at=NOW,
        payload_hash="sha256:" + "b" * 64,
        schema_version="1.0",
        is_synthetic=True,
    )
    assert event.aggregate_id == dispute.evidence_id


def test_audit_log_and_review_ticket_use_reason_codes() -> None:
    log = AgentDecisionLog(
        decision_id="decision-001",
        subject_id="synthetic-student-001",
        purpose=DecisionPurpose.FORMATIVE_PLANNING,
        input_hash="sha256:" + "a" * 64,
        evidence_ids=("evidence-001",),
        model_versions=("evidence-state/0.1.0",),
        knowledge_versions=("rules/2026-v1",),
        action=PublicationAction.HUMAN_REVIEW,
        reason_codes=("HIGH_STAKES_REQUIRES_HUMAN",),
        created_at=NOW,
        is_synthetic=True,
    )
    ticket = ReviewTicket(
        ticket_id="review-001",
        decision_id=log.decision_id,
        queue="career-counsellor",
        priority="HIGH",
        reason_codes=log.reason_codes,
        created_at=NOW,
        is_synthetic=True,
    )
    assert ticket.reason_codes == log.reason_codes
