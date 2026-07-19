from datetime import UTC, datetime

import pytest

from t3c2_path.algorithms.service_effect import (
    CausalObservation,
    MissingOutcomeStrategy,
    StudyDesign,
    TargetTrialSpec,
    TreatmentVariable,
    estimate_aipw,
    estimate_randomized_itt,
)
from t3c2_path.domain import ClaimLevel, PublicationAction

NOW = datetime(2026, 7, 19, 8, 0, tzinfo=UTC)


def trial(**overrides: object) -> TargetTrialSpec:
    data: dict[str, object] = {
        "trial_id": "synthetic-trial-001",
        "population_definition": "eligible synthetic students at time zero",
        "strategy_version": "service/0.1.0",
        "time_zero": NOW,
        "estimand": "ITT_ATE",
        "has_comparator": True,
        "stable_intervention": True,
        "minimum_overlap": 0.05,
        "study_design": StudyDesign.RANDOMIZED,
        "treatment_variable": TreatmentVariable.ASSIGNMENT,
        "exchangeability_supported": True,
        "missing_outcome_strategy": MissingOutcomeStrategy.UNADDRESSED,
        "is_synthetic": True,
    }
    data.update(overrides)
    return TargetTrialSpec(**data)


def observation(
    subject_id: str,
    assigned: bool,
    outcome: float,
    *,
    propensity: float = 0.5,
    m0: float = 50.0,
    m1: float = 53.0,
    received_service: bool | None = None,
    version: str = "service/0.1.0",
) -> CausalObservation:
    return CausalObservation(
        subject_id=subject_id,
        assigned=assigned,
        received_service=assigned if received_service is None else received_service,
        outcome=outcome,
        propensity=propensity,
        expected_outcome_no_service=m0,
        expected_outcome_service=m1,
        strategy_version=version,
        eligible=True,
        observed=True,
        is_synthetic=True,
    )


def test_randomized_itt_uses_assignment_despite_crossover() -> None:
    records = (
        observation("a1", True, 60, received_service=False),
        observation("a2", True, 58, received_service=True),
        observation("c1", False, 50, received_service=True),
        observation("c2", False, 52, received_service=False),
    )
    result = estimate_randomized_itt(trial(), records, created_at=NOW)
    assert result.action is PublicationAction.QUALIFIED
    assert result.report is not None
    assert result.report.estimate == 8.0
    assert "ASSIGNMENT_USE_CROSSOVER_PRESENT" in result.reason_codes


def test_aipw_recovers_known_constant_effect_when_nuisance_models_are_exact() -> None:
    records = tuple(
        observation(
            f"s{i}",
            assigned=i % 2 == 0,
            outcome=53.0 if i % 2 == 0 else 50.0,
        )
        for i in range(20)
    )
    result = estimate_aipw(trial(estimand="ATE"), records, created_at=NOW)
    assert result.action is PublicationAction.QUALIFIED
    assert result.report is not None
    assert result.report.estimate == pytest.approx(3.0)
    assert result.report.claim_level is ClaimLevel.SYNTHETIC_ONLY


def test_aipw_refuses_nonoverlap_instead_of_hiding_it_with_clipping() -> None:
    records = (
        observation("a", True, 53.0, propensity=0.999),
        observation("b", False, 50.0, propensity=0.001),
    )
    result = estimate_aipw(trial(), records, created_at=NOW)
    assert result.action is PublicationAction.DEFER
    assert result.report is None
    assert "POSITIVITY_VIOLATION" in result.reason_codes


def test_service_effect_refuses_mixed_intervention_versions() -> None:
    records = (
        observation("a", True, 53.0, version="service/0.1.0"),
        observation("b", False, 50.0, version="service/0.2.0"),
    )
    result = estimate_aipw(trial(), records, created_at=NOW)
    assert result.action is PublicationAction.DEFER
    assert result.report is None
    assert "MIXED_INTERVENTION_VERSIONS" in result.reason_codes


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"has_comparator": False}, "COMPARATOR_NOT_DEFINED"),
        ({"stable_intervention": False}, "INTERVENTION_VERSION_UNSTABLE"),
    ],
)
def test_target_trial_preconditions_are_executable(
    overrides: dict[str, object], reason: str
) -> None:
    records = (
        observation("a", True, 53.0),
        observation("b", False, 50.0),
    )
    result = estimate_aipw(trial(**overrides), records, created_at=NOW)
    assert result.action is PublicationAction.DEFER
    assert result.report is None
    assert reason in result.reason_codes


def test_observational_aipw_uses_received_service_and_cannot_auto_upgrade_to_causal() -> None:
    records = (
        observation("a", True, 50.0, received_service=False, m0=50.0, m1=53.0),
        observation("b", False, 53.0, received_service=True, m0=50.0, m1=53.0),
    )
    result = estimate_aipw(
        trial(
            study_design=StudyDesign.OBSERVATIONAL,
            treatment_variable=TreatmentVariable.RECEIVED_SERVICE,
            estimand="observational_AE",
            exchangeability_supported=False,
        ),
        records,
        created_at=NOW,
    )
    assert result.report is not None
    assert result.report.estimate == pytest.approx(3.0)
    assert result.report.claim_level is ClaimLevel.SYNTHETIC_ONLY
    assert "EXCHANGEABILITY_NOT_ESTABLISHED_NO_CAUSAL_CLAIM" in result.reason_codes


def test_real_observational_aipw_is_associational_even_with_overlap() -> None:
    records = tuple(
        observation(f"s{i}", i % 2 == 0, 53.0 if i % 2 == 0 else 50.0).model_copy(
            update={"is_synthetic": False}
        )
        for i in range(20)
    )
    result = estimate_aipw(
        trial(
            is_synthetic=False,
            study_design=StudyDesign.OBSERVATIONAL,
            treatment_variable=TreatmentVariable.RECEIVED_SERVICE,
            exchangeability_supported=False,
        ),
        records,
        created_at=NOW,
    )
    assert result.report is not None
    assert result.report.claim_level is ClaimLevel.ASSOCIATIONAL


def test_missing_outcomes_without_a_declared_strategy_force_defer() -> None:
    records = (
        observation("a", True, 53.0),
        observation("b", False, 50.0),
        observation("missing", True, 0.0).model_copy(update={"observed": False}),
    )
    result = estimate_randomized_itt(trial(), records, created_at=NOW)
    assert result.action is PublicationAction.DEFER
    assert "OUTCOME_MISSINGNESS_UNADDRESSED" in result.reason_codes


def test_exposure_after_outcome_is_excluded_from_effect_estimation() -> None:
    records = (
        observation("a", True, 53.0).model_copy(
            update={"exposure_at": NOW, "outcome_at": NOW}
        ),
        observation("b", False, 50.0).model_copy(
            update={"exposure_at": NOW, "outcome_at": NOW}
        ),
    )
    result = estimate_aipw(
        trial(
            study_design=StudyDesign.OBSERVATIONAL,
            treatment_variable=TreatmentVariable.RECEIVED_SERVICE,
        ),
        records,
        created_at=NOW,
    )
    assert result.action is PublicationAction.DEFER
    assert "EXPOSURE_NOT_BEFORE_OUTCOME" in result.reason_codes
