from datetime import UTC, datetime, timedelta

import pytest

from t3c2_path.algorithms.evidence_state import EvidenceStateEstimator
from t3c2_path.domain import EvidenceRecord, EvidenceStatus, SourceKind

NOW = datetime(2026, 7, 19, 8, 0, tzinfo=UTC)


def evidence(
    evidence_id: str,
    value: float | None,
    *,
    reliability: float = 0.8,
    age_days: float = 0.0,
    base_sd: float = 8.0,
    context: str = "general",
    duplicate_group: str | None = None,
) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=evidence_id,
        subject_id="synthetic-student-001",
        dimension="communication",
        observed_value=value,
        base_sd=base_sd,
        reliability=reliability,
        observed_at=NOW - timedelta(days=age_days),
        recorded_at=NOW,
        source_kind=SourceKind.WORK_SAMPLE,
        context=context,
        duplicate_group=duplicate_group,
        authorization_id="consent-001",
        status=EvidenceStatus.ACTIVE,
        is_synthetic=True,
    )


def test_effective_variance_rewards_reliability_and_penalizes_age_and_duplicates() -> None:
    estimator = EvidenceStateEstimator(as_of=NOW, half_life_days=56)
    reliable = estimator.effective_variance(evidence("reliable", 60, reliability=0.9))
    unreliable = estimator.effective_variance(evidence("unreliable", 60, reliability=0.4))
    old = estimator.effective_variance(evidence("old", 60, age_days=56))
    duplicate = estimator.effective_variance(
        evidence("duplicate", 60, duplicate_group="same-source"), duplicate_corr=0.7
    )
    assert reliable < unreliable
    assert old == pytest.approx(estimator.effective_variance(evidence("new", 60)) * 2)
    assert duplicate > estimator.effective_variance(evidence("independent", 60))


def test_unknown_and_withdrawn_evidence_are_skipped_not_scored_as_zero() -> None:
    estimator = EvidenceStateEstimator(as_of=NOW, half_life_days=56)
    withdrawn = evidence("withdrawn", 95).model_copy(update={"status": EvidenceStatus.WITHDRAWN})
    result = estimator.update(
        prior_mean=50,
        prior_sd=10,
        evidence_records=(evidence("unknown", None), withdrawn, evidence("active", 60)),
    )
    assert result.used_evidence_ids == ("active",)
    assert set(result.skipped_evidence_ids) == {"unknown", "withdrawn"}
    assert result.posterior_mean > 50


def test_robust_update_limits_an_extreme_outlier() -> None:
    estimator = EvidenceStateEstimator(as_of=NOW, half_life_days=56)
    result = estimator.update(
        prior_mean=50,
        prior_sd=5,
        evidence_records=(evidence("extreme", 100, base_sd=2, reliability=1.0),),
    )
    assert result.contributions[0].robust_weight < 1.0
    assert result.posterior_mean < 90


def test_context_conflict_is_split_instead_of_force_averaged() -> None:
    estimator = EvidenceStateEstimator(as_of=NOW, half_life_days=56)
    result = estimator.update_by_context(
        prior_mean=55,
        prior_sd=12,
        evidence_records=(
            evidence("formal-1", 44, context="formal_interview"),
            evidence("formal-2", 48, context="formal_interview"),
            evidence("team-1", 78, context="familiar_team"),
            evidence("team-2", 74, context="familiar_team"),
        ),
        conflict_threshold=15,
    )
    assert result.has_context_conflict
    assert result.context_results["formal_interview"].posterior_mean < 55
    assert result.context_results["familiar_team"].posterior_mean > 65


def test_update_is_deterministic_and_shrinks_uncertainty() -> None:
    estimator = EvidenceStateEstimator(as_of=NOW, half_life_days=56)
    records = (
        evidence("self", 72, reliability=0.45, age_days=14, base_sd=12),
        evidence("task", 61, reliability=0.90, age_days=7, base_sd=6),
        evidence("observer", 58, reliability=0.75, age_days=3.5, base_sd=8),
    )
    first = estimator.update(50, 10, records)
    second = estimator.update(50, 10, records)
    assert first == second
    assert first.posterior_sd < 10
