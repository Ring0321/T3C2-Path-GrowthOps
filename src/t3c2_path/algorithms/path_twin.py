"""Algorithm B: time-constrained, multi-path digital twin simulation."""

from __future__ import annotations

import math
import random
from datetime import datetime
from enum import StrEnum

from pydantic import Field, model_validator

from t3c2_path.clocks import PathClock
from t3c2_path.domain import FrozenModel, KnowledgeRule, PathStatus


class LatentDimension(FrozenModel):
    mean: float
    sd: float = Field(gt=0)


class PathRole(StrEnum):
    PRIMARY = "PRIMARY"
    SECONDARY = "SECONDARY"
    BACKUP = "BACKUP"


class PathTwinNodeStatus(StrEnum):
    LOCKED = "LOCKED"
    AVAILABLE = "AVAILABLE"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    BLOCKED = "BLOCKED"


class PathNodeDefinition(FrozenModel):
    node_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    due_at: datetime
    dependency_node_ids: tuple[str, ...] = ()
    required_asset_ids: tuple[str, ...] = ()
    produces_asset_ids: tuple[str, ...] = ()
    is_reversible: bool


class PathGraphDefinition(FrozenModel):
    path_id: str = Field(min_length=1)
    role: PathRole
    fit_score: float = Field(ge=0, le=100)
    nodes: tuple[PathNodeDefinition, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_graph(self) -> PathGraphDefinition:
        ids = [item.node_id for item in self.nodes]
        if len(ids) != len(set(ids)):
            raise ValueError("path node IDs must be unique")
        known = set(ids)
        for item in self.nodes:
            missing = set(item.dependency_node_ids) - known
            if missing:
                raise ValueError(f"unknown dependency node IDs: {sorted(missing)}")

        visiting: set[str] = set()
        visited: set[str] = set()
        dependency_map = {item.node_id: item.dependency_node_ids for item in self.nodes}

        def visit(node_id: str) -> None:
            if node_id in visiting:
                raise ValueError("path graph cannot contain a dependency cycle")
            if node_id in visited:
                return
            visiting.add(node_id)
            for dependency in dependency_map[node_id]:
                visit(dependency)
            visiting.remove(node_id)
            visited.add(node_id)

        for node_id in ids:
            visit(node_id)
        return self


class PathTwinEvent(FrozenModel):
    event_type: str = Field(pattern=r"^(COMPLETED|SWITCHED|ROLLED_BACK|DEADLINE_BLOCKED)$")
    occurred_at: datetime
    path_id: str = Field(min_length=1)
    node_id: str | None = None
    from_path_id: str | None = None
    to_path_id: str | None = None
    reason: str = Field(min_length=1)
    inherited_asset_ids: tuple[str, ...] = ()


class PathTwinState(FrozenModel):
    active_path_id: str = Field(min_length=1)
    definitions: tuple[PathGraphDefinition, ...] = Field(min_length=1)
    fit_by_path: dict[str, float]
    readiness_by_path: dict[str, float]
    node_statuses: dict[str, PathTwinNodeStatus]
    acquired_asset_ids: frozenset[str] = frozenset()
    history: tuple[PathTwinEvent, ...] = ()
    reason_codes: tuple[str, ...] = ()
    snapshot_version: int = Field(default=1, ge=1)


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
    context: str = Field(default="general", min_length=1)


def _definition_map(state: PathTwinState) -> dict[str, PathGraphDefinition]:
    return {item.path_id: item for item in state.definitions}


def _node_map(state: PathTwinState) -> dict[str, tuple[str, PathNodeDefinition]]:
    return {
        node.node_id: (definition.path_id, node)
        for definition in state.definitions
        for node in definition.nodes
    }


def _recompute_node_statuses(
    state: PathTwinState, *, as_of: datetime
) -> tuple[dict[str, PathTwinNodeStatus], tuple[PathTwinEvent, ...], tuple[str, ...]]:
    statuses = dict(state.node_statuses)
    events: list[PathTwinEvent] = []
    reasons = list(state.reason_codes)
    nodes = _node_map(state)
    for node_id, (path_id, node) in nodes.items():
        current = statuses[node_id]
        if current is PathTwinNodeStatus.COMPLETED:
            continue
        if node.due_at < as_of:
            if current is not PathTwinNodeStatus.BLOCKED:
                events.append(
                    PathTwinEvent(
                        event_type="DEADLINE_BLOCKED",
                        occurred_at=as_of,
                        path_id=path_id,
                        node_id=node_id,
                        reason="hard deadline passed before completion",
                    )
                )
            statuses[node_id] = PathTwinNodeStatus.BLOCKED
            if "DEADLINE_EXPIRED" not in reasons:
                reasons.append("DEADLINE_EXPIRED")
            continue
        dependencies_complete = all(
            statuses[item] is PathTwinNodeStatus.COMPLETED
            for item in node.dependency_node_ids
        )
        assets_available = set(node.required_asset_ids) <= set(state.acquired_asset_ids)
        statuses[node_id] = (
            PathTwinNodeStatus.AVAILABLE
            if dependencies_complete and assets_available
            else PathTwinNodeStatus.LOCKED
        )
    return statuses, tuple(events), tuple(reasons)


def initialize_path_twin(
    definitions: tuple[PathGraphDefinition, ...],
    *,
    readiness_by_path: dict[str, float],
    as_of: datetime,
) -> PathTwinState:
    if as_of.tzinfo is None:
        raise ValueError("as_of must be timezone-aware")
    path_ids = {item.path_id for item in definitions}
    if len(path_ids) != len(definitions):
        raise ValueError("path IDs must be unique")
    primary = [item.path_id for item in definitions if item.role is PathRole.PRIMARY]
    if len(primary) != 1:
        raise ValueError("exactly one primary path is required")
    if set(readiness_by_path) != path_ids:
        raise ValueError("readiness must be supplied for every path")
    if any(not 0 <= item <= 100 for item in readiness_by_path.values()):
        raise ValueError("readiness scores must lie in [0, 100]")
    node_ids = [node.node_id for item in definitions for node in item.nodes]
    if len(node_ids) != len(set(node_ids)):
        raise ValueError("node IDs must be globally unique across paths")
    state = PathTwinState(
        active_path_id=primary[0],
        definitions=definitions,
        fit_by_path={item.path_id: item.fit_score for item in definitions},
        readiness_by_path=readiness_by_path,
        node_statuses={item: PathTwinNodeStatus.LOCKED for item in node_ids},
    )
    return refresh_path_twin(state, as_of=as_of)


def refresh_path_twin(state: PathTwinState, *, as_of: datetime) -> PathTwinState:
    if as_of.tzinfo is None:
        raise ValueError("as_of must be timezone-aware")
    statuses, events, reasons = _recompute_node_statuses(state, as_of=as_of)
    return state.model_copy(
        update={
            "node_statuses": statuses,
            "history": (*state.history, *events),
            "reason_codes": reasons,
            "snapshot_version": state.snapshot_version + 1,
        }
    )


def advance_path_twin(
    state: PathTwinState,
    *,
    path_id: str,
    node_id: str,
    occurred_at: datetime,
) -> PathTwinState:
    if path_id != state.active_path_id:
        raise ValueError("only the active path can be advanced")
    nodes = _node_map(state)
    if node_id not in nodes or nodes[node_id][0] != path_id:
        raise ValueError("node does not belong to the selected path")
    if state.node_statuses[node_id] not in {
        PathTwinNodeStatus.AVAILABLE,
        PathTwinNodeStatus.IN_PROGRESS,
    }:
        raise ValueError("node is not available for completion")
    node = nodes[node_id][1]
    statuses = dict(state.node_statuses)
    statuses[node_id] = PathTwinNodeStatus.COMPLETED
    assets = frozenset(set(state.acquired_asset_ids) | set(node.produces_asset_ids))
    updated = state.model_copy(
        update={
            "node_statuses": statuses,
            "acquired_asset_ids": assets,
            "history": (
                *state.history,
                PathTwinEvent(
                    event_type="COMPLETED",
                    occurred_at=occurred_at,
                    path_id=path_id,
                    node_id=node_id,
                    reason="completion criteria and evidence requirement satisfied",
                    inherited_asset_ids=tuple(sorted(node.produces_asset_ids)),
                ),
            ),
            "snapshot_version": state.snapshot_version + 1,
        }
    )
    return refresh_path_twin(updated, as_of=occurred_at)


def switch_path_twin(
    state: PathTwinState,
    *,
    to_path_id: str,
    occurred_at: datetime,
    reason: str,
) -> PathTwinState:
    if to_path_id not in _definition_map(state):
        raise ValueError("unknown target path")
    if to_path_id == state.active_path_id:
        raise ValueError("target path is already active")
    event = PathTwinEvent(
        event_type="SWITCHED",
        occurred_at=occurred_at,
        path_id=to_path_id,
        from_path_id=state.active_path_id,
        to_path_id=to_path_id,
        reason=reason,
        inherited_asset_ids=tuple(sorted(state.acquired_asset_ids)),
    )
    switched = state.model_copy(
        update={
            "active_path_id": to_path_id,
            "history": (*state.history, event),
            "snapshot_version": state.snapshot_version + 1,
        }
    )
    return refresh_path_twin(switched, as_of=occurred_at)


def rollback_path_twin(
    state: PathTwinState, *, occurred_at: datetime, reason: str
) -> PathTwinState:
    previous = next(
        (
            item
            for item in reversed(state.history)
            if item.event_type == "SWITCHED" and item.to_path_id == state.active_path_id
        ),
        None,
    )
    if previous is None or previous.from_path_id is None:
        raise ValueError("no reversible path switch exists")
    event = PathTwinEvent(
        event_type="ROLLED_BACK",
        occurred_at=occurred_at,
        path_id=previous.from_path_id,
        from_path_id=state.active_path_id,
        to_path_id=previous.from_path_id,
        reason=reason,
        inherited_asset_ids=tuple(sorted(state.acquired_asset_ids)),
    )
    rolled_back = state.model_copy(
        update={
            "active_path_id": previous.from_path_id,
            "history": (*state.history, event),
            "snapshot_version": state.snapshot_version + 1,
        }
    )
    return refresh_path_twin(rolled_back, as_of=occurred_at)


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
    "PathGraphDefinition",
    "PathNodeDefinition",
    "PathRole",
    "PathSimulationResult",
    "PathTwinEvent",
    "PathTwinNodeStatus",
    "PathTwinState",
    "advance_path_twin",
    "initialize_path_twin",
    "pareto_front",
    "refresh_path_twin",
    "rollback_path_twin",
    "simulate_paths",
    "switch_path_twin",
]
