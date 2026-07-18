from datetime import UTC, datetime

import pytest

from t3c2_path.algorithms.value_added import VARequest, estimate_student_value_added
from t3c2_path.domain import ClaimLevel, PublicationAction

NOW = datetime(2026, 7, 19, 8, 0, tzinfo=UTC)


def request(**overrides: object) -> VARequest:
    data: dict[str, object] = {
        "report_id": "va-synthetic-001",
        "subject_id": "synthetic-student-001",
        "observed_readiness": 65.0,
        "observed_standard_error": 1.5,
        "expected_readiness": 60.0,
        "expected_standard_error": 2.0,
        "reference_definition": "same stage, track and baseline band",
        "reference_sample_size": 120,
        "measurement_invariant": True,
        "model_version": "va/0.1.0",
        "created_at": NOW,
        "is_synthetic": True,
    }
    data.update(overrides)
    return VARequest(**data)


def test_va_is_observed_minus_expected_with_propagated_uncertainty() -> None:
    result = estimate_student_value_added(request())
    assert result.action is PublicationAction.QUALIFIED
    assert result.report is not None
    assert result.report.estimate == 5.0
    expected_se = (1.5**2 + 2.0**2) ** 0.5
    assert result.standard_error == expected_se
    assert result.report.interval_low == pytest.approx(5.0 - 1.96 * expected_se)
    assert result.report.interval_high == pytest.approx(5.0 + 1.96 * expected_se)
    assert result.report.claim_level is ClaimLevel.SYNTHETIC_ONLY


def test_va_stops_cross_group_comparison_when_measurement_is_not_invariant() -> None:
    result = estimate_student_value_added(request(measurement_invariant=False))
    assert result.action is PublicationAction.DEFER
    assert result.report is None
    assert "MEASUREMENT_INVARIANCE_NOT_ESTABLISHED" in result.reason_codes


def test_va_defers_when_reference_sample_is_too_small() -> None:
    result = estimate_student_value_added(request(reference_sample_size=12))
    assert result.action is PublicationAction.DEFER
    assert result.report is None
    assert "REFERENCE_SAMPLE_TOO_SMALL" in result.reason_codes


def test_wide_va_interval_is_reported_as_uncertain_not_no_growth() -> None:
    result = estimate_student_value_added(
        request(observed_standard_error=10.0, expected_standard_error=10.0)
    )
    assert result.action is PublicationAction.DEFER
    assert result.report is None
    assert "INTERVAL_TOO_WIDE_FOR_INDIVIDUAL_INTERPRETATION" in result.reason_codes


def test_real_data_request_never_escalates_va_to_service_causality() -> None:
    result = estimate_student_value_added(request(is_synthetic=False))
    assert result.report is not None
    assert result.report.claim_level is ClaimLevel.FORMATIVE
