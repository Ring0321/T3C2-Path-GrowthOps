"""Algorithm D: formative student value-added with uncertainty propagation."""

from __future__ import annotations

import math

from pydantic import AwareDatetime, Field

from t3c2_path.domain import (
    ClaimLevel,
    FrozenModel,
    PublicationAction,
    StudentValueAddedReport,
)


class MeasurementInvarianceAssessment(FrozenModel):
    method: str = Field(min_length=1)
    grouping_dimensions: tuple[str, ...] = Field(min_length=1)
    established: bool
    specification_stable: bool
    assessed_at: AwareDatetime


class VARequest(FrozenModel):
    report_id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    observed_readiness: float
    observed_standard_error: float = Field(ge=0)
    expected_readiness: float
    expected_standard_error: float = Field(ge=0)
    reference_definition: str = Field(min_length=1)
    reference_sample_size: int = Field(ge=0)
    measurement_invariant: bool
    measurement_assessment: MeasurementInvarianceAssessment | None = None
    reference_time_split: str | None = Field(default=None, min_length=1)
    model_specification_frozen: bool = False
    model_version: str = Field(min_length=1)
    created_at: AwareDatetime
    is_synthetic: bool
class VAResult(FrozenModel):
    action: PublicationAction
    report: StudentValueAddedReport | None
    standard_error: float | None = Field(default=None, ge=0)
    reason_codes: tuple[str, ...] = Field(min_length=1)


def estimate_student_value_added(
    request: VARequest,
    *,
    minimum_reference_sample: int = 30,
    maximum_interval_width: float = 20.0,
) -> VAResult:
    """Estimate observed-minus-expected readiness for formative use only.

    The expected trajectory is supplied by an upstream, cross-fitted reference
    model.  This function propagates uncertainty and enforces publication
    conditions; it does not train the reference model.
    """

    reasons: list[str] = []
    if not request.measurement_invariant:
        reasons.append("MEASUREMENT_INVARIANCE_NOT_ESTABLISHED")
    if request.measurement_assessment is None:
        reasons.append("MEASUREMENT_INVARIANCE_EVIDENCE_MISSING")
    else:
        if not request.measurement_assessment.established:
            reasons.append("MEASUREMENT_INVARIANCE_NOT_ESTABLISHED")
        if not request.measurement_assessment.specification_stable:
            reasons.append("MEASUREMENT_INVARIANCE_SPECIFICATION_UNSTABLE")
    if request.reference_time_split is None:
        reasons.append("REFERENCE_TIME_SPLIT_MISSING")
    if not request.model_specification_frozen:
        reasons.append("REFERENCE_MODEL_SPECIFICATION_NOT_FROZEN")
    if request.reference_sample_size < minimum_reference_sample:
        reasons.append("REFERENCE_SAMPLE_TOO_SMALL")
    if reasons:
        return VAResult(action=PublicationAction.DEFER, report=None, reason_codes=tuple(reasons))

    estimate = request.observed_readiness - request.expected_readiness
    standard_error = math.sqrt(
        request.observed_standard_error**2 + request.expected_standard_error**2
    )
    interval_low = estimate - 1.96 * standard_error
    interval_high = estimate + 1.96 * standard_error
    if interval_high - interval_low > maximum_interval_width:
        return VAResult(
            action=PublicationAction.DEFER,
            report=None,
            standard_error=standard_error,
            reason_codes=("INTERVAL_TOO_WIDE_FOR_INDIVIDUAL_INTERPRETATION",),
        )

    claim_level = ClaimLevel.SYNTHETIC_ONLY if request.is_synthetic else ClaimLevel.FORMATIVE
    report = StudentValueAddedReport(
        report_id=request.report_id,
        subject_id=request.subject_id,
        observed_readiness=request.observed_readiness,
        expected_readiness=request.expected_readiness,
        estimate=estimate,
        interval_low=interval_low,
        interval_high=interval_high,
        reference_definition=request.reference_definition,
        model_version=request.model_version,
        claim_level=claim_level,
        created_at=request.created_at,
        is_synthetic=request.is_synthetic,
    )
    return VAResult(
        action=PublicationAction.QUALIFIED,
        report=report,
        standard_error=standard_error,
        reason_codes=("FORMATIVE_VA_WITH_UNCERTAINTY",),
    )


__all__ = [
    "MeasurementInvarianceAssessment",
    "VARequest",
    "VAResult",
    "estimate_student_value_added",
]
