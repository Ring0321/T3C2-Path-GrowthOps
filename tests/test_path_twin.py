from datetime import UTC, datetime, timedelta

from t3c2_path.algorithms.path_twin import (
    LatentDimension,
    PathDefinition,
    PathGraphDefinition,
    PathNodeDefinition,
    PathRole,
    PathTwinNodeStatus,
    advance_path_twin,
    initialize_path_twin,
    pareto_front,
    refresh_path_twin,
    rollback_path_twin,
    simulate_paths,
    switch_path_twin,
)
from t3c2_path.domain import KnowledgeRule, PathStatus

NOW = datetime(2026, 7, 19, 8, 0, tzinfo=UTC)


def rule(rule_id: str, valid: bool = True) -> KnowledgeRule:
    return KnowledgeRule(
        rule_id=rule_id,
        track_id="track-a",
        rule_type="hard_eligibility",
        expression="synthetic == true",
        source_url="https://example.invalid/rule",
        source_version="synthetic/1",
        valid_from=NOW - timedelta(days=30),
        valid_to=NOW + timedelta(days=30) if valid else NOW - timedelta(days=1),
        retrieved_at=NOW,
        is_synthetic=True,
    )


def definition(path_id: str, hard_rule_ids: tuple[str, ...] = ()) -> PathDefinition:
    return PathDefinition(
        path_id=path_id,
        requirements={"analysis": 60.0, "communication": 60.0},
        weights={"analysis": 0.5, "communication": 0.5},
        weekly_workload_hours=12.0,
        transferability=75.0,
        window_days=90,
        hard_rule_ids=hard_rule_ids,
        critical_margin=15.0,
    )


def states(mean: float) -> dict[str, LatentDimension]:
    return {
        "analysis": LatentDimension(mean=mean, sd=5.0),
        "communication": LatentDimension(mean=mean, sd=5.0),
    }


def test_path_simulation_is_reproducible_with_an_explicit_seed() -> None:
    first = simulate_paths(states(62), (definition("market"),), (), NOW, draws=500, seed=7)
    second = simulate_paths(states(62), (definition("market"),), (), NOW, draws=500, seed=7)
    assert first == second


def test_expired_hard_rule_blocks_probability_instead_of_being_a_soft_penalty() -> None:
    result = simulate_paths(
        states(80),
        (definition("civil-service", hard_rule_ids=("eligibility",)),),
        (rule("eligibility", valid=False),),
        NOW,
        draws=200,
        seed=7,
    )[0]
    assert result.status is PathStatus.NEEDS_VERIFICATION
    assert result.feasibility_probability is None
    assert "eligibility" in result.invalid_rule_ids


def test_improving_every_dimension_does_not_reduce_readiness() -> None:
    low = simulate_paths(states(50), (definition("market"),), (), NOW, draws=2_000, seed=7)[0]
    high = simulate_paths(states(70), (definition("market"),), (), NOW, draws=2_000, seed=7)[0]
    assert high.expected_readiness > low.expected_readiness
    assert high.feasibility_probability is not None
    assert low.feasibility_probability is not None
    assert high.feasibility_probability >= low.feasibility_probability


def test_pareto_front_keeps_tradeoffs_and_removes_dominated_options() -> None:
    front = pareto_front(
        (
            ("balanced", 80.0, 0.8, 80.0, 12.0),
            ("lower-burden", 76.0, 0.75, 78.0, 6.0),
            ("dominated", 70.0, 0.6, 60.0, 15.0),
        )
    )
    assert front == frozenset({"balanced", "lower-burden"})


def graph(
    path_id: str, role: PathRole, *, fit: float, deadline_days: int = 30
) -> PathGraphDefinition:
    return PathGraphDefinition(
        path_id=path_id,
        role=role,
        fit_score=fit,
        nodes=(
            PathNodeDefinition(
                node_id=f"{path_id}:explore",
                title="minimum action experiment",
                due_at=NOW + timedelta(days=deadline_days),
                produces_asset_ids=("portfolio-evidence",),
                is_reversible=True,
            ),
            PathNodeDefinition(
                node_id=f"{path_id}:commit",
                title="bounded commitment",
                due_at=NOW + timedelta(days=deadline_days + 30),
                dependency_node_ids=(f"{path_id}:explore",),
                required_asset_ids=("portfolio-evidence",),
                is_reversible=True,
            ),
        ),
    )


def test_path_twin_executes_dependencies_deadlines_switch_and_rollback() -> None:
    primary = graph("market", PathRole.PRIMARY, fit=82)
    backup = graph("exam", PathRole.BACKUP, fit=74)
    state = initialize_path_twin(
        (primary, backup),
        readiness_by_path={"market": 61.0, "exam": 48.0},
        as_of=NOW,
    )
    assert state.fit_by_path["market"] == 82
    assert state.readiness_by_path["market"] == 61
    assert state.node_statuses["market:commit"] is PathTwinNodeStatus.LOCKED

    completed = advance_path_twin(
        state,
        path_id="market",
        node_id="market:explore",
        occurred_at=NOW + timedelta(days=1),
    )
    assert "portfolio-evidence" in completed.acquired_asset_ids
    assert completed.node_statuses["market:commit"] is PathTwinNodeStatus.AVAILABLE

    switched = switch_path_twin(
        completed,
        to_path_id="exam",
        occurred_at=NOW + timedelta(days=2),
        reason="new preference evidence",
    )
    assert switched.active_path_id == "exam"
    assert "portfolio-evidence" in switched.acquired_asset_ids
    rolled_back = rollback_path_twin(
        switched,
        occurred_at=NOW + timedelta(days=3),
        reason="exam rule window changed",
    )
    assert rolled_back.active_path_id == "market"
    assert [item.event_type for item in rolled_back.history][-2:] == ["SWITCHED", "ROLLED_BACK"]


def test_path_twin_blocks_overdue_nodes_instead_of_treating_time_as_a_soft_score() -> None:
    overdue = graph("overdue", PathRole.PRIMARY, fit=80, deadline_days=-1)
    state = initialize_path_twin(
        (overdue,), readiness_by_path={"overdue": 90.0}, as_of=NOW
    )
    refreshed = refresh_path_twin(state, as_of=NOW)
    assert refreshed.node_statuses["overdue:explore"] is PathTwinNodeStatus.BLOCKED
    assert "DEADLINE_EXPIRED" in refreshed.reason_codes
