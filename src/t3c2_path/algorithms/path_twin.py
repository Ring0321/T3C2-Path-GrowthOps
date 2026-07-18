"""Algorithm B: time-constrained, multi-path digital twin simulation."""

from __future__ import annotations

import math
import random
from datetime import datetime

from pydantic import Field, model_validator

from t3c2_path.clocks import PathClock
from t3c2_path.domain import FrozenModel, KnowledgeRule, PathStatus


class LatentDimension(FrozenModel):
    mean: float
    sd: float = Field(gt=0)


class PathDefinition(FrozenModel):
    path_id: str = Field(min_length=1)
    requirements: dict[str, float] = Field(min_length=1)
    weights: dict[str, float] = Field(min_length=1)
    weekly_workload_hours: float = Field(ge=0)
    transferability: float = Field(ge=0, le=100)
    window_days: int = Field(gt=0)
    hard_rule_ids: tuple[str, ...] = ()
    critical_margin: float = Field(ge=0)
    readiness_threshold: float = Field(default=78.0, ge=0, le=100)

    @model_validator(mode="after")
    def validate_dimensions(self) -> PathDefinition:
        if set(self.requirements) != set(self.weights):
            raise ValueError("requirements and weights must use the same dimensions")
        if not math.isclose(sum(self.weights.values()), 1.0, abs_tol=1e-8):
            raise ValueError("path weights must sum to 1")
        if any(weight < 0 for weight in self.weights.values()):
            raise ValueError("path weights cannot be negative")
        return self


class PathSimulationResult(FrozenModel):
    path_id: str
    status: PathStatus
    expected_readiness: float = Field(ge=0, le=100)
    readiness_sd: float = Field(ge=0)
    p10_readiness: float = Field(ge=0, le=100)
    p90_readiness: float = Field(ge=0, le=100)
    feasibility_probability: float | None = Field(default=None, ge=0, le=1)
    risk_index: float | None = Field(default=None, ge=0, le=100)
    weekly_workload_hours: float = Field(ge=0)
    transferability: float = Field(ge=0, le=100)
    window_days: int = Field(gt=0)
    invalid_rule_ids: tuple[str, ...]
    pareto_front: bool = False
    seed: int
    draws: int = Field(gt=0)


def _quantile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def pareto_front(
    options: tuple[tuple[str, float, float, float, float], ...],
) -> frozenset[str]:
    """Return non-dominated IDs.

    Tuple order is id, readiness, feasibility, transferability, workload.  The
    first three objectives are maximized and workload is minimized.
    """

    keep: set[str] = set()
    for option in options:
        option_id, readiness, feasibility, transferability, workload = option
        dominated = False
        for challenger in options:
            if challenger[0] == option_id:
                continue
            at_least_as_good = (
                challenger[1] >= readiness
                and challenger[2] >= feasibility
                and challenger[3] >= transferability
                and challenger[4] <= workload
            )
            strictly_better = (
                challenger[1] > readiness
                or challenger[2] > feasibility
                or challenger[3] > transferability
                or challenger[4] < workload
            )
            if at_least_as_good and strictly_better:
                dominated = True
                break
        if not dominated:
            keep.add(option_id)
    return frozenset(keep)


def simulate_paths(
    states: dict[str, LatentDimension],
    definitions: tuple[PathDefinition, ...],
    rules: tuple[KnowledgeRule, ...],
    as_of: datetime,
    *,
    draws: int = 5_000,
    seed: int = 20260719,
) -> tuple[PathSimulationResult, ...]:
    if draws <= 0:
        raise ValueError("draws must be positive")
    required_dimensions = {name for item in definitions for name in item.requirements}
    missing_dimensions = required_dimensions - states.keys()
    if missing_dimensions:
        raise ValueError(f"missing latent dimensions: {sorted(missing_dimensions)}")

    rng = random.Random(seed)
    dimension_names = sorted(states)
    state_draws = [
        {name: rng.gauss(states[name].mean, states[name].sd) for name in dimension_names}
        for _ in range(draws)
    ]
    rule_by_id = {rule.rule_id: rule for rule in rules}
    clock = PathClock(as_of)
    preliminary: list[PathSimulationResult] = []

    for definition in definitions:
        referenced_rules = tuple(
            rule_by_id[rule_id]
            for rule_id in definition.hard_rule_ids
            if rule_id in rule_by_id
        )
        audit = clock.audit_rules(referenced_rules)
        missing_rules = tuple(
            sorted(set(definition.hard_rule_ids) - set(rule_by_id))
        )
        invalid_rules = tuple(
            sorted(
                set(audit.expired_rule_ids)
                | set(audit.not_yet_valid_rule_ids)
                | set(missing_rules)
            )
        )
        readiness_values: list[float] = []
        feasible_count = 0
        for sample in state_draws:
            weighted_shortfall = sum(
                max(definition.requirements[name] - sample[name], 0.0)
                * definition.weights[name]
                for name in definition.requirements
            )
            readiness = min(100.0, max(0.0, 100.0 - 2.25 * weighted_shortfall))
            readiness_values.append(readiness)
            critical_ok = all(
                sample[name]
                >= definition.requirements[name] - definition.critical_margin
                for name in definition.requirements
            )
            if readiness >= definition.readiness_threshold and critical_ok:
                feasible_count += 1

        expected = sum(readiness_values) / draws
        variance = sum((value - expected) ** 2 for value in readiness_values) / max(draws - 1, 1)
        if invalid_rules:
            status = PathStatus.NEEDS_VERIFICATION
            feasibility_probability = None
            risk_index = None
        else:
            status = PathStatus.FEASIBLE
            feasibility_probability = feasible_count / draws
            risk_index = 100.0 * (1.0 - feasibility_probability)
        preliminary.append(
            PathSimulationResult(
                path_id=definition.path_id,
                status=status,
                expected_readiness=expected,
                readiness_sd=math.sqrt(variance),
                p10_readiness=_quantile(readiness_values, 0.10),
                p90_readiness=_quantile(readiness_values, 0.90),
                feasibility_probability=feasibility_probability,
                risk_index=risk_index,
                weekly_workload_hours=definition.weekly_workload_hours,
                transferability=definition.transferability,
                window_days=definition.window_days,
                invalid_rule_ids=invalid_rules,
                seed=seed,
                draws=draws,
            )
        )

    front_candidates = tuple(
        (
            result.path_id,
            result.expected_readiness,
            result.feasibility_probability,
            result.transferability,
            result.weekly_workload_hours,
        )
        for result in preliminary
        if result.feasibility_probability is not None
    )
    front_ids = pareto_front(front_candidates)
    return tuple(
        item.model_copy(update={"pareto_front": item.path_id in front_ids})
        for item in preliminary
    )


__all__ = [
    "LatentDimension",
    "PathDefinition",
    "PathSimulationResult",
    "pareto_front",
    "simulate_paths",
]
