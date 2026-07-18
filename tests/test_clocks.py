from datetime import UTC, datetime, timedelta

import pytest

from t3c2_path.clocks import EvidenceClock, PathClock, ServiceClock
from t3c2_path.domain import KnowledgeRule, ServiceExposure

NOW = datetime(2026, 7, 19, 8, 0, tzinfo=UTC)


def rule(rule_id: str, start: datetime, end: datetime) -> KnowledgeRule:
    return KnowledgeRule(
        rule_id=rule_id,
        track_id="synthetic-track",
        rule_type="hard_eligibility",
        expression="synthetic == true",
        source_url="https://example.invalid/synthetic-rule",
        source_version="synthetic/1",
        valid_from=start,
        valid_to=end,
        retrieved_at=NOW,
        is_synthetic=True,
    )


def exposure(exposure_id: str, version: str, assigned: bool, dose: float) -> ServiceExposure:
    return ServiceExposure(
        exposure_id=exposure_id,
        subject_id="synthetic-student-001",
        service_id="synthetic-service",
        strategy_version=version,
        assigned=assigned,
        started_at=NOW,
        ended_at=None,
        dose=dose,
        recorded_at=NOW,
        is_synthetic=True,
    )


def test_evidence_freshness_halves_at_the_declared_half_life() -> None:
    clock = EvidenceClock(as_of=NOW)
    observed_at = NOW - timedelta(days=30)
    assert clock.freshness(observed_at, half_life_days=30) == pytest.approx(0.5)


def test_future_evidence_is_rejected_instead_of_receiving_extra_weight() -> None:
    clock = EvidenceClock(as_of=NOW)
    with pytest.raises(ValueError, match="future"):
        clock.freshness(NOW + timedelta(seconds=1), half_life_days=30)


def test_path_clock_separates_valid_expired_and_not_yet_valid_rules() -> None:
    audit = PathClock(as_of=NOW).audit_rules(
        (
            rule("valid", NOW - timedelta(days=1), NOW + timedelta(days=1)),
            rule("expired", NOW - timedelta(days=2), NOW - timedelta(days=1)),
            rule("future", NOW + timedelta(days=1), NOW + timedelta(days=2)),
        )
    )
    assert audit.valid_rule_ids == ("valid",)
    assert audit.expired_rule_ids == ("expired",)
    assert audit.not_yet_valid_rule_ids == ("future",)
    assert not audit.can_auto_publish


def test_service_clock_does_not_replace_assignment_with_actual_use() -> None:
    audit = ServiceClock(as_of=NOW).audit_exposures(
        (
            exposure("e1", "service/1", assigned=True, dose=0.0),
            exposure("e2", "service/1", assigned=False, dose=2.0),
        )
    )
    assert audit.assigned_count == 1
    assert audit.exposed_count == 1
    assert audit.has_assignment_use_crossover


def test_service_clock_detects_mixed_strategy_versions() -> None:
    audit = ServiceClock(as_of=NOW).audit_exposures(
        (
            exposure("e1", "service/1", assigned=True, dose=1.0),
            exposure("e2", "service/2", assigned=True, dose=1.0),
        )
    )
    assert audit.has_mixed_versions
    assert audit.strategy_versions == ("service/1", "service/2")
