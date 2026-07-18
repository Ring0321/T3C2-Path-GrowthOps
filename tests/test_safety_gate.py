from t3c2_path.algorithms.safety_gate import (
    GatePolicy,
    GroupAuditObservation,
    PublicationCandidate,
    calibration_metrics,
    evaluate_publication,
    fairness_audit,
    risk_coverage_curve,
)
from t3c2_path.domain import DecisionPurpose, PublicationAction


def candidate(**overrides: object) -> PublicationCandidate:
    data: dict[str, object] = {
        "candidate_id": "candidate-001",
        "purpose": DecisionPurpose.FORMATIVE_PLANNING,
        "consent_valid": True,
        "evidence_coverage": 0.8,
        "rules_valid": True,
        "calibration_ece": 0.04,
        "fairness_gap": 0.05,
        "uncertainty_width": 8.0,
        "student_workload_hours": 2.0,
        "is_high_stakes": False,
    }
    data.update(overrides)
    return PublicationCandidate(**data)


def test_good_low_risk_candidate_can_publish() -> None:
    result = evaluate_publication(candidate(), GatePolicy())
    assert result.action is PublicationAction.PUBLISH
    assert result.reason_codes == ("ALL_PUBLICATION_GATES_PASSED",)


def test_invalid_consent_blocks_before_any_soft_quality_score() -> None:
    result = evaluate_publication(candidate(consent_valid=False), GatePolicy())
    assert result.action is PublicationAction.BLOCK
    assert "CONSENT_INVALID" in result.reason_codes


def test_high_stakes_purpose_always_routes_to_human_review() -> None:
    result = evaluate_publication(
        candidate(purpose=DecisionPurpose.HIGH_STAKES, is_high_stakes=True), GatePolicy()
    )
    assert result.action is PublicationAction.HUMAN_REVIEW
    assert "HIGH_STAKES_REQUIRES_HUMAN" in result.reason_codes


def test_stale_rule_and_poor_calibration_defer_with_specific_remediation() -> None:
    result = evaluate_publication(
        candidate(rules_valid=False, calibration_ece=0.3), GatePolicy()
    )
    assert result.action is PublicationAction.DEFER
    assert set(result.reason_codes) >= {"KNOWLEDGE_RULE_INVALID", "CALIBRATION_FAILED"}
    assert set(result.required_actions) >= {"VERIFY_KNOWLEDGE_RULES", "RECALIBRATE_MODEL"}


def test_calibration_metrics_report_brier_and_expected_calibration_error() -> None:
    metrics = calibration_metrics(
        probabilities=(0.9, 0.8, 0.2, 0.1), outcomes=(1, 1, 0, 0), bins=2
    )
    assert metrics.brier_score < 0.05
    assert 0 <= metrics.expected_calibration_error <= 1
    assert sum(item.count for item in metrics.bins) == 4


def test_selective_coverage_reduces_risk_when_confidence_is_informative() -> None:
    curve = risk_coverage_curve(
        confidences=(0.95, 0.9, 0.4, 0.3), correct=(True, True, False, False)
    )
    full = next(point for point in curve if point.coverage == 1.0)
    half = next(point for point in curve if point.coverage == 0.5)
    assert half.risk < full.risk


def test_fairness_gap_routes_to_human_not_silent_group_thresholding() -> None:
    result = evaluate_publication(candidate(fairness_gap=0.30), GatePolicy())
    assert result.action is PublicationAction.HUMAN_REVIEW
    assert "FAIRNESS_REVIEW_REQUIRED" in result.reason_codes


def test_fairness_audit_checks_error_coverage_and_burden_not_only_accuracy() -> None:
    records = (
        GroupAuditObservation(group="A", correct=True, published=True, task_burden=2.0),
        GroupAuditObservation(group="A", correct=True, published=True, task_burden=2.0),
        GroupAuditObservation(group="B", correct=False, published=True, task_burden=5.0),
        GroupAuditObservation(group="B", correct=False, published=False, task_burden=7.0),
    )
    audit = fairness_audit(records, minimum_group_size=2)
    assert audit.is_estimable
    assert audit.maximum_error_rate_gap == 1.0
    assert audit.maximum_coverage_gap == 0.5
    assert audit.maximum_mean_burden_gap == 4.0


def test_fairness_audit_refuses_tiny_groups() -> None:
    audit = fairness_audit(
        (GroupAuditObservation(group="A", correct=True, published=True, task_burden=1.0),),
        minimum_group_size=2,
    )
    assert not audit.is_estimable
    assert audit.insufficient_group_ids == ("A",)
