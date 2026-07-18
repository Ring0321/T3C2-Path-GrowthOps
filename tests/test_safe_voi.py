from t3c2_path.algorithms.safe_voi import SafeVOIPolicy, TaskCandidate, rank_tasks


def candidate(task_id: str, **overrides: object) -> TaskCandidate:
    data: dict[str, object] = {
        "task_id": task_id,
        "expected_growth": 7.0,
        "information_gain": 7.0,
        "transferability": 7.0,
        "window_rescue": 5.0,
        "burden": 3.0,
        "risk": 2.0,
        "estimated_hours": 1.0,
        "monetary_cost": 0.0,
        "consent_valid": True,
        "rules_valid": True,
        "is_reversible": True,
        "is_high_stakes": False,
        "is_paid_service": False,
    }
    data.update(overrides)
    return TaskCandidate(**data)


def test_safety_gate_cannot_be_offset_by_a_high_value_score() -> None:
    high_value_but_unsafe = candidate(
        "unsafe",
        expected_growth=10,
        information_gain=10,
        transferability=10,
        window_rescue=10,
        consent_valid=False,
    )
    decision = rank_tasks((high_value_but_unsafe,), SafeVOIPolicy())[0]
    assert decision.gate == "BLOCK"
    assert decision.publishable_value is None
    assert "CONSENT_INVALID" in decision.reason_codes


def test_low_cost_informative_action_dominates_a_paid_commitment() -> None:
    interview = candidate("interview", information_gain=8, estimated_hours=1, monetary_cost=0)
    course = candidate(
        "paid-course",
        information_gain=6,
        estimated_hours=20,
        monetary_cost=5_000,
        is_paid_service=True,
    )
    decisions = {item.task_id: item for item in rank_tasks((interview, course), SafeVOIPolicy())}
    assert decisions["interview"].gate == "PASS"
    assert decisions["paid-course"].gate == "BLOCK"
    assert "LOWER_COST_INFORMATION_DOMINATES" in decisions["paid-course"].reason_codes


def test_passed_tasks_are_ranked_only_after_gating() -> None:
    high_info = candidate("high-info", information_gain=9)
    low_info = candidate("low-info", information_gain=4)
    unsafe = candidate("unsafe", information_gain=10, is_high_stakes=True)
    decisions = rank_tasks((low_info, unsafe, high_info), SafeVOIPolicy())
    passed = [item for item in decisions if item.gate == "PASS"]
    blocked = [item for item in decisions if item.gate == "BLOCK"]
    assert [item.task_id for item in passed] == ["high-info", "low-info"]
    assert blocked[0].task_id == "unsafe"
    assert blocked[0].rank is None


def test_value_formula_matches_the_preregistered_transparent_weights() -> None:
    task = candidate(
        "manual-check",
        expected_growth=8,
        information_gain=9.5,
        transferability=6,
        window_rescue=10,
        burden=2,
        risk=1,
    )
    decision = rank_tasks((task,), SafeVOIPolicy())[0]
    expected = 0.30 * 8 + 0.25 * 9.5 + 0.20 * 6 + 0.15 * 10 - 0.10 * 2 - 0.15 * 1
    assert decision.raw_value == expected
