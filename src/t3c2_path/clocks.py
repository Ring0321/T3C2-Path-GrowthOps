"""Explicit time semantics for evidence, paths and service exposure."""

from __future__ import annotations

import math
from datetime import datetime

from pydantic import AwareDatetime, Field

from t3c2_path.domain import FrozenModel, KnowledgeRule, ServiceExposure


class RuleClockAudit(FrozenModel):
    as_of: AwareDatetime
    valid_rule_ids: tuple[str, ...]
    expired_rule_ids: tuple[str, ...]
    not_yet_valid_rule_ids: tuple[str, ...]

    @property
    def can_auto_publish(self) -> bool:
        return not self.expired_rule_ids and not self.not_yet_valid_rule_ids


class ServiceClockAudit(FrozenModel):
    as_of: AwareDatetime
    assigned_count: int = Field(ge=0)
    exposed_count: int = Field(ge=0)
    crossover_count: int = Field(ge=0)
    strategy_versions: tuple[str, ...]

    @property
    def has_assignment_use_crossover(self) -> bool:
        return self.crossover_count > 0

    @property
    def has_mixed_versions(self) -> bool:
        return len(self.strategy_versions) > 1


class EvidenceClock:
    def __init__(self, as_of: datetime) -> None:
        if as_of.tzinfo is None:
            raise ValueError("as_of must be timezone-aware")
        self.as_of = as_of

    def age_days(self, observed_at: datetime) -> float:
        if observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        age = (self.as_of - observed_at).total_seconds() / 86_400
        if age < 0:
            raise ValueError("future evidence is not valid at this decision time")
        return age

    def freshness(self, observed_at: datetime, half_life_days: float) -> float:
        if half_life_days <= 0:
            raise ValueError("half_life_days must be positive")
        return math.pow(2.0, -self.age_days(observed_at) / half_life_days)


class PathClock:
    def __init__(self, as_of: datetime) -> None:
        if as_of.tzinfo is None:
            raise ValueError("as_of must be timezone-aware")
        self.as_of = as_of

    def audit_rules(self, rules: tuple[KnowledgeRule, ...]) -> RuleClockAudit:
        valid: list[str] = []
        expired: list[str] = []
        future: list[str] = []
        for rule in rules:
            if self.as_of < rule.valid_from:
                future.append(rule.rule_id)
            elif self.as_of > rule.valid_to:
                expired.append(rule.rule_id)
            else:
                valid.append(rule.rule_id)
        return RuleClockAudit(
            as_of=self.as_of,
            valid_rule_ids=tuple(sorted(valid)),
            expired_rule_ids=tuple(sorted(expired)),
            not_yet_valid_rule_ids=tuple(sorted(future)),
        )


class ServiceClock:
    def __init__(self, as_of: datetime) -> None:
        if as_of.tzinfo is None:
            raise ValueError("as_of must be timezone-aware")
        self.as_of = as_of

    def audit_exposures(self, exposures: tuple[ServiceExposure, ...]) -> ServiceClockAudit:
        assigned_count = sum(item.assigned for item in exposures)
        exposed_count = sum(item.dose > 0 for item in exposures)
        crossover_count = sum(item.assigned != (item.dose > 0) for item in exposures)
        versions = tuple(sorted({item.strategy_version for item in exposures}))
        return ServiceClockAudit(
            as_of=self.as_of,
            assigned_count=assigned_count,
            exposed_count=exposed_count,
            crossover_count=crossover_count,
            strategy_versions=versions,
        )


__all__ = [
    "EvidenceClock",
    "PathClock",
    "RuleClockAudit",
    "ServiceClock",
    "ServiceClockAudit",
]
