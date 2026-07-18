"""Algorithm A: evidence-calibrated dynamic latent state.

The implementation is intentionally transparent.  Reliability, evidence age
and duplicated origin alter observation variance; robust weighting limits a
single extreme observation.  These mechanics are research defaults, not
validated production parameters.
"""

from __future__ import annotations

import math
from datetime import datetime

from pydantic import AwareDatetime, Field

from t3c2_path.clocks import EvidenceClock
from t3c2_path.domain import EvidenceRecord, EvidenceStatus, FrozenModel


class EvidenceContribution(FrozenModel):
    evidence_id: str
    effective_variance: float = Field(gt=0)
    robust_weight: float = Field(gt=0, le=1)
    posterior_mean: float
    posterior_sd: float = Field(gt=0)


class EvidenceStateResult(FrozenModel):
    as_of: AwareDatetime
    posterior_mean: float
    posterior_sd: float = Field(gt=0)
    interval_low: float
    interval_high: float
    used_evidence_ids: tuple[str, ...]
    skipped_evidence_ids: tuple[str, ...]
    contributions: tuple[EvidenceContribution, ...]


class ContextEvidenceResult(FrozenModel):
    as_of: AwareDatetime
    context_results: dict[str, EvidenceStateResult]
    has_context_conflict: bool
    maximum_mean_gap: float = Field(ge=0)


class EvidenceStateEstimator:
    """Sequential normal update with a Huber-like residual weight."""

    def __init__(
        self,
        as_of: datetime,
        half_life_days: float,
        *,
        duplicate_correlation: float = 0.65,
        reliability_floor: float = 0.10,
        robust_cutoff: float = 2.5,
    ) -> None:
        if half_life_days <= 0:
            raise ValueError("half_life_days must be positive")
        if not 0 <= duplicate_correlation <= 1:
            raise ValueError("duplicate_correlation must lie in [0, 1]")
        if not 0 < reliability_floor <= 1:
            raise ValueError("reliability_floor must lie in (0, 1]")
        if robust_cutoff <= 0:
            raise ValueError("robust_cutoff must be positive")
        self.clock = EvidenceClock(as_of)
        self.half_life_days = half_life_days
        self.duplicate_correlation = duplicate_correlation
        self.reliability_floor = reliability_floor
        self.robust_cutoff = robust_cutoff

    @property
    def as_of(self) -> datetime:
        return self.clock.as_of

    def effective_variance(
        self, record: EvidenceRecord, *, duplicate_corr: float = 0.0
    ) -> float:
        if not 0 <= duplicate_corr <= 1:
            raise ValueError("duplicate_corr must lie in [0, 1]")
        age_days = self.clock.age_days(record.observed_at)
        age_inflation = math.pow(2.0, age_days / self.half_life_days)
        return (
            record.base_sd**2
            / max(record.reliability, self.reliability_floor)
            * age_inflation
            * (1.0 + duplicate_corr)
        )

    def update(
        self,
        prior_mean: float,
        prior_sd: float,
        evidence_records: tuple[EvidenceRecord, ...],
    ) -> EvidenceStateResult:
        if prior_sd <= 0:
            raise ValueError("prior_sd must be positive")
        mean = prior_mean
        variance = prior_sd**2
        used: list[str] = []
        skipped: list[str] = []
        contributions: list[EvidenceContribution] = []
        seen_duplicate_groups: set[str] = set()

        for record in evidence_records:
            if record.status is not EvidenceStatus.ACTIVE or record.observed_value is None:
                skipped.append(record.evidence_id)
                continue
            duplicate_corr = 0.0
            if record.duplicate_group is not None:
                if record.duplicate_group in seen_duplicate_groups:
                    duplicate_corr = self.duplicate_correlation
                seen_duplicate_groups.add(record.duplicate_group)
            observation_variance = self.effective_variance(
                record, duplicate_corr=duplicate_corr
            )
            mean, variance, robust_weight = self._normal_update(
                mean, variance, record.observed_value, observation_variance
            )
            used.append(record.evidence_id)
            contributions.append(
                EvidenceContribution(
                    evidence_id=record.evidence_id,
                    effective_variance=observation_variance,
                    robust_weight=robust_weight,
                    posterior_mean=mean,
                    posterior_sd=math.sqrt(variance),
                )
            )

        sd = math.sqrt(variance)
        return EvidenceStateResult(
            as_of=self.as_of,
            posterior_mean=mean,
            posterior_sd=sd,
            interval_low=mean - 1.96 * sd,
            interval_high=mean + 1.96 * sd,
            used_evidence_ids=tuple(used),
            skipped_evidence_ids=tuple(skipped),
            contributions=tuple(contributions),
        )

    def update_by_context(
        self,
        prior_mean: float,
        prior_sd: float,
        evidence_records: tuple[EvidenceRecord, ...],
        *,
        conflict_threshold: float,
    ) -> ContextEvidenceResult:
        if conflict_threshold < 0:
            raise ValueError("conflict_threshold must be non-negative")
        grouped: dict[str, list[EvidenceRecord]] = {}
        for record in evidence_records:
            grouped.setdefault(record.context, []).append(record)
        context_results = {
            context: self.update(prior_mean, prior_sd, tuple(records))
            for context, records in sorted(grouped.items())
        }
        means = [item.posterior_mean for item in context_results.values()]
        maximum_gap = max(means) - min(means) if means else 0.0
        return ContextEvidenceResult(
            as_of=self.as_of,
            context_results=context_results,
            has_context_conflict=maximum_gap > conflict_threshold,
            maximum_mean_gap=maximum_gap,
        )

    def _normal_update(
        self, mean: float, variance: float, observation: float, observation_variance: float
    ) -> tuple[float, float, float]:
        residual = observation - mean
        scale = math.sqrt(variance + observation_variance)
        robust_weight = 1.0
        if abs(residual) > self.robust_cutoff * scale:
            robust_weight = self.robust_cutoff * scale / abs(residual)
        precision = 1.0 / variance + robust_weight / observation_variance
        new_variance = 1.0 / precision
        new_mean = new_variance * (
            mean / variance + robust_weight * observation / observation_variance
        )
        return new_mean, new_variance, robust_weight


__all__ = [
    "ContextEvidenceResult",
    "EvidenceContribution",
    "EvidenceStateEstimator",
    "EvidenceStateResult",
]
