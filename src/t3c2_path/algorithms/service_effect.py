"""Algorithm E: group-level service-effect estimators with executable boundaries."""

from __future__ import annotations

import math
from enum import StrEnum

from pydantic import AwareDatetime, Field

from t3c2_path.domain import (
    ClaimLevel,
    FrozenModel,
    PublicationAction,
    ServiceEffectReport,
)


class StudyDesign(StrEnum):
    RANDOMIZED = "RANDOMIZED"
    QUASI_EXPERIMENTAL = "QUASI_EXPERIMENTAL"
    OBSERVATIONAL = "OBSERVATIONAL"


class TreatmentVariable(StrEnum):
    ASSIGNMENT = "ASSIGNMENT"
    RECEIVED_SERVICE = "RECEIVED_SERVICE"


class MissingOutcomeStrategy(StrEnum):
    UNADDRESSED = "UNADDRESSED"
    COMPLETE_CASE = "COMPLETE_CASE"
    EXTERNALLY_ADJUSTED = "EXTERNALLY_ADJUSTED"


class TargetTrialSpec(FrozenModel):
    trial_id: str = Field(min_length=1)
    population_definition: str = Field(min_length=1)
    strategy_version: str = Field(min_length=1)
    time_zero: AwareDatetime
    estimand: str = Field(min_length=1)
    has_comparator: bool
    stable_intervention: bool
    minimum_overlap: float = Field(gt=0, lt=0.5)
    study_design: StudyDesign
    treatment_variable: TreatmentVariable
    exchangeability_supported: bool
    missing_outcome_strategy: MissingOutcomeStrategy
    is_synthetic: bool


class CausalObservation(FrozenModel):
    subject_id: str = Field(min_length=1)
    assigned: bool
    received_service: bool
    outcome: float
    propensity: float = Field(gt=0, lt=1)
    expected_outcome_no_service: float
    expected_outcome_service: float
    strategy_version: str = Field(min_length=1)
    eligible: bool
    observed: bool
    is_synthetic: bool
    exposure_at: AwareDatetime | None = None
    outcome_at: AwareDatetime | None = None


class EffectEstimationResult(FrozenModel):
    action: PublicationAction
    report: ServiceEffectReport | None
    standard_error: float | None = Field(default=None, ge=0)
    analyzed_n: int = Field(ge=0)
    reason_codes: tuple[str, ...] = Field(min_length=1)


def _sample_variance(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return sum((value - mean) ** 2 for value in values) / (len(values) - 1)


def _preconditions(
    trial: TargetTrialSpec, records: tuple[CausalObservation, ...]
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not trial.has_comparator:
        reasons.append("COMPARATOR_NOT_DEFINED")
    if not trial.stable_intervention:
        reasons.append("INTERVENTION_VERSION_UNSTABLE")
    versions = {item.strategy_version for item in records}
    if versions != {trial.strategy_version}:
        reasons.append("MIXED_INTERVENTION_VERSIONS")
    if any(
        item.exposure_at is not None
        and item.outcome_at is not None
        and item.exposure_at >= item.outcome_at
        for item in records
        if item.eligible
    ):
        reasons.append("EXPOSURE_NOT_BEFORE_OUTCOME")
    missing_outcomes = any(item.eligible and not item.observed for item in records)
    if (
        missing_outcomes
        and trial.missing_outcome_strategy is MissingOutcomeStrategy.UNADDRESSED
    ):
        reasons.append("OUTCOME_MISSINGNESS_UNADDRESSED")
    return tuple(reasons)


def _claim_level(
    trial: TargetTrialSpec, records: tuple[CausalObservation, ...]
) -> ClaimLevel:
    if trial.is_synthetic and all(item.is_synthetic for item in records):
        return ClaimLevel.SYNTHETIC_ONLY
    if trial.study_design is StudyDesign.OBSERVATIONAL:
        return ClaimLevel.ASSOCIATIONAL
    if (
        trial.study_design is StudyDesign.QUASI_EXPERIMENTAL
        and not trial.exchangeability_supported
    ):
        return ClaimLevel.ASSOCIATIONAL
    if trial.missing_outcome_strategy is MissingOutcomeStrategy.COMPLETE_CASE:
        return ClaimLevel.ASSOCIATIONAL
    return ClaimLevel.CAUSAL_GROUP


def estimate_randomized_itt(
    trial: TargetTrialSpec,
    records: tuple[CausalObservation, ...],
    *,
    created_at: AwareDatetime,
) -> EffectEstimationResult:
    failures = list(_preconditions(trial, records))
    if trial.study_design is not StudyDesign.RANDOMIZED:
        failures.append("ITT_REQUIRES_RANDOMIZED_ASSIGNMENT")
    if trial.treatment_variable is not TreatmentVariable.ASSIGNMENT:
        failures.append("ITT_REQUIRES_ASSIGNMENT_VARIABLE")
    eligible = tuple(item for item in records if item.eligible and item.observed)
    treated = [item.outcome for item in eligible if item.assigned]
    control = [item.outcome for item in eligible if not item.assigned]
    if failures:
        return EffectEstimationResult(
            action=PublicationAction.DEFER,
            report=None,
            analyzed_n=len(eligible),
            reason_codes=tuple(dict.fromkeys(failures)),
        )
    if len(treated) < 2 or len(control) < 2:
        return EffectEstimationResult(
            action=PublicationAction.DEFER,
            report=None,
            analyzed_n=len(eligible),
            reason_codes=("INSUFFICIENT_RANDOMIZED_GROUP_SIZE",),
        )

    estimate = sum(treated) / len(treated) - sum(control) / len(control)
    standard_error = math.sqrt(
        _sample_variance(treated) / len(treated) + _sample_variance(control) / len(control)
    )
    reasons = ["RANDOMIZED_ITT_ESTIMATED"]
    if any(item.assigned != item.received_service for item in eligible):
        reasons.append("ASSIGNMENT_USE_CROSSOVER_PRESENT")
    report = ServiceEffectReport(
        report_id=f"{trial.trial_id}:itt",
        population_definition=trial.population_definition,
        strategy_version=trial.strategy_version,
        estimand=trial.estimand,
        estimate=estimate,
        interval_low=estimate - 1.96 * standard_error,
        interval_high=estimate + 1.96 * standard_error,
        overlap_min=0.0,
        overlap_max=1.0,
        claim_level=_claim_level(trial, eligible),
        created_at=created_at,
        is_synthetic=_claim_level(trial, eligible) is ClaimLevel.SYNTHETIC_ONLY,
    )
    return EffectEstimationResult(
        action=PublicationAction.QUALIFIED,
        report=report,
        standard_error=standard_error,
        analyzed_n=len(eligible),
        reason_codes=tuple(reasons),
    )


def estimate_aipw(
    trial: TargetTrialSpec,
    records: tuple[CausalObservation, ...],
    *,
    created_at: AwareDatetime,
) -> EffectEstimationResult:
    failures = list(_preconditions(trial, records))
    if (
        trial.study_design is StudyDesign.OBSERVATIONAL
        and trial.treatment_variable is not TreatmentVariable.RECEIVED_SERVICE
    ):
        failures.append("OBSERVATIONAL_AIPW_REQUIRES_SERVICE_RECEIPT")
    eligible = tuple(item for item in records if item.eligible and item.observed)
    if len(eligible) < 2:
        failures.append("INSUFFICIENT_ANALYSIS_SAMPLE")
    if eligible:
        minimum = min(item.propensity for item in eligible)
        maximum = max(item.propensity for item in eligible)
        if minimum < trial.minimum_overlap or maximum > 1.0 - trial.minimum_overlap:
            failures.append("POSITIVITY_VIOLATION")
    else:
        minimum = maximum = 0.0
    if failures:
        return EffectEstimationResult(
            action=PublicationAction.DEFER,
            report=None,
            analyzed_n=len(eligible),
            reason_codes=tuple(dict.fromkeys(failures)),
        )

    pseudo_outcomes: list[float] = []
    for item in eligible:
        treatment = 1.0 if (
            item.assigned
            if trial.treatment_variable is TreatmentVariable.ASSIGNMENT
            else item.received_service
        ) else 0.0
        pseudo_outcomes.append(
            item.expected_outcome_service
            - item.expected_outcome_no_service
            + treatment
            * (item.outcome - item.expected_outcome_service)
            / item.propensity
            - (1.0 - treatment)
            * (item.outcome - item.expected_outcome_no_service)
            / (1.0 - item.propensity)
        )
    estimate = sum(pseudo_outcomes) / len(pseudo_outcomes)
    standard_error = math.sqrt(_sample_variance(pseudo_outcomes) / len(pseudo_outcomes))
    claim_level = _claim_level(trial, eligible)
    report = ServiceEffectReport(
        report_id=f"{trial.trial_id}:aipw",
        population_definition=trial.population_definition,
        strategy_version=trial.strategy_version,
        estimand=trial.estimand,
        estimate=estimate,
        interval_low=estimate - 1.96 * standard_error,
        interval_high=estimate + 1.96 * standard_error,
        overlap_min=minimum,
        overlap_max=maximum,
        claim_level=claim_level,
        created_at=created_at,
        is_synthetic=claim_level is ClaimLevel.SYNTHETIC_ONLY,
    )
    reasons = ["AIPW_ESTIMATE_WITH_OVERLAP_DIAGNOSTICS"]
    if not trial.exchangeability_supported:
        reasons.append("EXCHANGEABILITY_NOT_ESTABLISHED_NO_CAUSAL_CLAIM")
    return EffectEstimationResult(
        action=PublicationAction.QUALIFIED,
        report=report,
        standard_error=standard_error,
        analyzed_n=len(eligible),
        reason_codes=tuple(reasons),
    )


__all__ = [
    "CausalObservation",
    "EffectEstimationResult",
    "MissingOutcomeStrategy",
    "StudyDesign",
    "TargetTrialSpec",
    "TreatmentVariable",
    "estimate_aipw",
    "estimate_randomized_itt",
]
