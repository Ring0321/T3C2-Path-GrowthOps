"""Algorithm F: calibration, fairness and selective publication gates."""

from __future__ import annotations

from pydantic import Field

from t3c2_path.domain import DecisionPurpose, FrozenModel, PublicationAction


class CalibrationBin(FrozenModel):
    lower: float = Field(ge=0, le=1)
    upper: float = Field(ge=0, le=1)
    count: int = Field(ge=0)
    mean_probability: float = Field(ge=0, le=1)
    observed_rate: float = Field(ge=0, le=1)


class CalibrationMetrics(FrozenModel):
    brier_score: float = Field(ge=0, le=1)
    expected_calibration_error: float = Field(ge=0, le=1)
    bins: tuple[CalibrationBin, ...]


class RiskCoveragePoint(FrozenModel):
    coverage: float = Field(gt=0, le=1)
    risk: float = Field(ge=0, le=1)
    threshold: float = Field(ge=0, le=1)


class GroupAuditObservation(FrozenModel):
    group: str = Field(min_length=1)
    correct: bool
    published: bool
    task_burden: float = Field(ge=0)


class GroupAuditMetric(FrozenModel):
    group: str
    count: int = Field(ge=1)
    error_rate_among_published: float | None = Field(default=None, ge=0, le=1)
    coverage: float = Field(ge=0, le=1)
    mean_task_burden: float = Field(ge=0)


class FairnessAudit(FrozenModel):
    is_estimable: bool
    group_metrics: tuple[GroupAuditMetric, ...]
    insufficient_group_ids: tuple[str, ...]
    maximum_error_rate_gap: float = Field(ge=0, le=1)
    maximum_coverage_gap: float = Field(ge=0, le=1)
    maximum_mean_burden_gap: float = Field(ge=0)


class PublicationCandidate(FrozenModel):
    candidate_id: str = Field(min_length=1)
    purpose: DecisionPurpose
    consent_valid: bool
    evidence_coverage: float = Field(ge=0, le=1)
    rules_valid: bool
    calibration_ece: float = Field(ge=0, le=1)
    fairness_gap: float = Field(ge=0, le=1)
    uncertainty_width: float = Field(ge=0)
    student_workload_hours: float = Field(ge=0)
    is_high_stakes: bool
    context_conflict: bool = False


class GatePolicy(FrozenModel):
    minimum_evidence_coverage: float = Field(default=0.60, ge=0, le=1)
    maximum_calibration_ece: float = Field(default=0.10, ge=0, le=1)
    maximum_fairness_gap: float = Field(default=0.15, ge=0, le=1)
    maximum_uncertainty_width: float = Field(default=25.0, ge=0)
    maximum_workload_hours: float = Field(default=10.0, ge=0)


class GateResult(FrozenModel):
    candidate_id: str
    action: PublicationAction
    reason_codes: tuple[str, ...] = Field(min_length=1)
    required_actions: tuple[str, ...]


def calibration_metrics(
    probabilities: tuple[float, ...], outcomes: tuple[int | bool, ...], *, bins: int = 10
) -> CalibrationMetrics:
    if len(probabilities) != len(outcomes) or not probabilities:
        raise ValueError("probabilities and outcomes must be non-empty and equal length")
    if bins <= 0:
        raise ValueError("bins must be positive")
    if any(not 0 <= value <= 1 for value in probabilities):
        raise ValueError("probabilities must lie in [0, 1]")
    if any(value not in (0, 1, False, True) for value in outcomes):
        raise ValueError("outcomes must be binary")

    n = len(probabilities)
    brier = (
        sum(
            (probability - int(outcome)) ** 2
            for probability, outcome in zip(probabilities, outcomes, strict=True)
        )
        / n
    )
    grouped: list[list[tuple[float, int]]] = [[] for _ in range(bins)]
    for probability, outcome in zip(probabilities, outcomes, strict=True):
        index = min(int(probability * bins), bins - 1)
        grouped[index].append((probability, int(outcome)))

    result_bins: list[CalibrationBin] = []
    ece = 0.0
    for index, items in enumerate(grouped):
        if not items:
            continue
        mean_probability = sum(item[0] for item in items) / len(items)
        observed_rate = sum(item[1] for item in items) / len(items)
        ece += len(items) / n * abs(mean_probability - observed_rate)
        result_bins.append(
            CalibrationBin(
                lower=index / bins,
                upper=(index + 1) / bins,
                count=len(items),
                mean_probability=mean_probability,
                observed_rate=observed_rate,
            )
        )
    return CalibrationMetrics(
        brier_score=brier,
        expected_calibration_error=ece,
        bins=tuple(result_bins),
    )


def risk_coverage_curve(
    confidences: tuple[float, ...], correct: tuple[bool, ...]
) -> tuple[RiskCoveragePoint, ...]:
    if len(confidences) != len(correct) or not confidences:
        raise ValueError("confidences and correct must be non-empty and equal length")
    if any(not 0 <= value <= 1 for value in confidences):
        raise ValueError("confidences must lie in [0, 1]")
    ranked = sorted(zip(confidences, correct, strict=True), key=lambda item: item[0], reverse=True)
    points: list[RiskCoveragePoint] = []
    for count in range(1, len(ranked) + 1):
        selected = ranked[:count]
        points.append(
            RiskCoveragePoint(
                coverage=count / len(ranked),
                risk=1.0 - sum(item[1] for item in selected) / count,
                threshold=selected[-1][0],
            )
        )
    return tuple(points)


def fairness_audit(
    records: tuple[GroupAuditObservation, ...], *, minimum_group_size: int = 20
) -> FairnessAudit:
    """Audit error, selective coverage and support burden by group.

    Sensitive attributes are used only in an isolated audit context.  The
    function reports disparities; it does not alter individual predictions or
    silently set different group thresholds.
    """

    if minimum_group_size <= 0:
        raise ValueError("minimum_group_size must be positive")
    grouped: dict[str, list[GroupAuditObservation]] = {}
    for record in records:
        grouped.setdefault(record.group, []).append(record)
    metrics: list[GroupAuditMetric] = []
    insufficient: list[str] = []
    for group, items in sorted(grouped.items()):
        if len(items) < minimum_group_size:
            insufficient.append(group)
        published = [item for item in items if item.published]
        error_rate = (
            1.0 - sum(item.correct for item in published) / len(published)
            if published
            else None
        )
        metrics.append(
            GroupAuditMetric(
                group=group,
                count=len(items),
                error_rate_among_published=error_rate,
                coverage=len(published) / len(items),
                mean_task_burden=sum(item.task_burden for item in items) / len(items),
            )
        )
    error_rates = [
        item.error_rate_among_published
        for item in metrics
        if item.error_rate_among_published is not None
    ]
    coverages = [item.coverage for item in metrics]
    burdens = [item.mean_task_burden for item in metrics]

    def gap(values: list[float]) -> float:
        return max(values) - min(values) if len(values) >= 2 else 0.0

    return FairnessAudit(
        is_estimable=bool(metrics) and not insufficient,
        group_metrics=tuple(metrics),
        insufficient_group_ids=tuple(insufficient),
        maximum_error_rate_gap=gap(error_rates),
        maximum_coverage_gap=gap(coverages),
        maximum_mean_burden_gap=gap(burdens),
    )


def evaluate_publication(
    candidate: PublicationCandidate, policy: GatePolicy
) -> GateResult:
    reasons: list[str] = []
    actions: list[str] = []
    if not candidate.consent_valid:
        reasons.append("CONSENT_INVALID")
        actions.append("RENEW_OR_CORRECT_CONSENT")
    if candidate.purpose is DecisionPurpose.HIGH_STAKES or candidate.is_high_stakes:
        reasons.append("HIGH_STAKES_REQUIRES_HUMAN")
        actions.append("CREATE_HUMAN_REVIEW_TICKET")
    if candidate.context_conflict:
        reasons.append("CONTEXT_CONFLICT_REQUIRES_DISCRIMINATING_EVIDENCE")
        actions.append("PRESERVE_CONTEXTS_AND_RUN_DISCRIMINATING_TASK")
    if not candidate.rules_valid:
        reasons.append("KNOWLEDGE_RULE_INVALID")
        actions.append("VERIFY_KNOWLEDGE_RULES")
    if candidate.evidence_coverage < policy.minimum_evidence_coverage:
        reasons.append("EVIDENCE_COVERAGE_INSUFFICIENT")
        actions.append("COLLECT_MINIMUM_ADDITIONAL_EVIDENCE")
    if candidate.calibration_ece > policy.maximum_calibration_ece:
        reasons.append("CALIBRATION_FAILED")
        actions.append("RECALIBRATE_MODEL")
    if candidate.fairness_gap > policy.maximum_fairness_gap:
        reasons.append("FAIRNESS_REVIEW_REQUIRED")
        actions.append("AUDIT_GROUP_ERRORS_AND_ACCESS")
    if candidate.uncertainty_width > policy.maximum_uncertainty_width:
        reasons.append("UNCERTAINTY_TOO_WIDE")
        actions.append("DEFER_AND_COLLECT_EVIDENCE")
    if candidate.student_workload_hours > policy.maximum_workload_hours:
        reasons.append("WORKLOAD_REVIEW_REQUIRED")
        actions.append("REDUCE_OR_HUMAN_REVIEW_WORKLOAD")

    if not reasons:
        return GateResult(
            candidate_id=candidate.candidate_id,
            action=PublicationAction.PUBLISH,
            reason_codes=("ALL_PUBLICATION_GATES_PASSED",),
            required_actions=(),
        )
    if "CONSENT_INVALID" in reasons:
        action = PublicationAction.BLOCK
    elif any(
        reason in reasons
        for reason in (
            "HIGH_STAKES_REQUIRES_HUMAN",
            "FAIRNESS_REVIEW_REQUIRED",
            "WORKLOAD_REVIEW_REQUIRED",
        )
    ):
        action = PublicationAction.HUMAN_REVIEW
    else:
        action = PublicationAction.DEFER
    return GateResult(
        candidate_id=candidate.candidate_id,
        action=action,
        reason_codes=tuple(reasons),
        required_actions=tuple(actions),
    )


__all__ = [
    "CalibrationBin",
    "CalibrationMetrics",
    "FairnessAudit",
    "GatePolicy",
    "GateResult",
    "GroupAuditMetric",
    "GroupAuditObservation",
    "PublicationCandidate",
    "RiskCoveragePoint",
    "calibration_metrics",
    "evaluate_publication",
    "fairness_audit",
    "risk_coverage_curve",
]
