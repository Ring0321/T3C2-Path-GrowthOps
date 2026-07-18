"""Algorithm C: safe expected-value-of-information task selection."""

from __future__ import annotations

from pydantic import Field

from t3c2_path.domain import FrozenModel

Score = float


class TaskCandidate(FrozenModel):
    task_id: str = Field(min_length=1)
    expected_growth: Score = Field(ge=0, le=10)
    information_gain: Score = Field(ge=0, le=10)
    transferability: Score = Field(ge=0, le=10)
    window_rescue: Score = Field(ge=0, le=10)
    burden: Score = Field(ge=0, le=10)
    risk: Score = Field(ge=0, le=10)
    estimated_hours: float = Field(ge=0)
    monetary_cost: float = Field(ge=0)
    consent_valid: bool
    rules_valid: bool
    is_reversible: bool
    is_high_stakes: bool
    is_paid_service: bool


class SafeVOIPolicy(FrozenModel):
    growth_weight: float = 0.30
    information_weight: float = 0.25
    transferability_weight: float = 0.20
    window_weight: float = 0.15
    burden_weight: float = 0.10
    risk_weight: float = 0.15
    paid_minimum_information: float = 5.0


class TaskDecision(FrozenModel):
    task_id: str
    gate: str = Field(pattern=r"^(PASS|BLOCK)$")
    raw_value: float
    publishable_value: float | None
    reason_codes: tuple[str, ...]
    rank: int | None = Field(default=None, ge=1)


def _raw_value(candidate: TaskCandidate, policy: SafeVOIPolicy) -> float:
    return (
        policy.growth_weight * candidate.expected_growth
        + policy.information_weight * candidate.information_gain
        + policy.transferability_weight * candidate.transferability
        + policy.window_weight * candidate.window_rescue
        - policy.burden_weight * candidate.burden
        - policy.risk_weight * candidate.risk
    )


def _dominant_lower_cost_action(
    candidate: TaskCandidate, alternatives: tuple[TaskCandidate, ...]
) -> TaskCandidate | None:
    for alternative in alternatives:
        if alternative.task_id == candidate.task_id:
            continue
        no_more_costly = (
            alternative.monetary_cost <= candidate.monetary_cost
            and alternative.estimated_hours <= candidate.estimated_hours
        )
        no_less_informative = alternative.information_gain >= candidate.information_gain
        strictly_better = (
            alternative.monetary_cost < candidate.monetary_cost
            or alternative.estimated_hours < candidate.estimated_hours
            or alternative.information_gain > candidate.information_gain
        )
        if no_more_costly and no_less_informative and strictly_better:
            return alternative
    return None


def rank_tasks(
    candidates: tuple[TaskCandidate, ...], policy: SafeVOIPolicy
) -> tuple[TaskDecision, ...]:
    decisions: list[TaskDecision] = []
    for candidate in candidates:
        reasons: list[str] = []
        if not candidate.consent_valid:
            reasons.append("CONSENT_INVALID")
        if not candidate.rules_valid:
            reasons.append("KNOWLEDGE_RULE_INVALID")
        if not candidate.is_reversible:
            reasons.append("ACTION_NOT_REVERSIBLE")
        if candidate.is_high_stakes:
            reasons.append("HIGH_STAKES_REQUIRES_HUMAN")
        if (
            candidate.is_paid_service
            and candidate.information_gain < policy.paid_minimum_information
        ):
            reasons.append("PAID_ACTION_LOW_INFORMATION")
        if candidate.is_paid_service and _dominant_lower_cost_action(candidate, candidates):
            reasons.append("LOWER_COST_INFORMATION_DOMINATES")
        raw_value = _raw_value(candidate, policy)
        passed_gate = not reasons
        decisions.append(
            TaskDecision(
                task_id=candidate.task_id,
                gate="PASS" if passed_gate else "BLOCK",
                raw_value=raw_value,
                publishable_value=raw_value if passed_gate else None,
                reason_codes=tuple(reasons) if reasons else ("SAFE_BASELINE_PASSED",),
            )
        )

    passed_decisions = sorted(
        (item for item in decisions if item.gate == "PASS"),
        key=lambda item: (-item.raw_value, item.task_id),
    )
    ranked_passed = [
        item.model_copy(update={"rank": rank})
        for rank, item in enumerate(passed_decisions, 1)
    ]
    blocked = sorted(
        (item for item in decisions if item.gate == "BLOCK"),
        key=lambda item: (-item.raw_value, item.task_id),
    )
    return tuple(ranked_passed + blocked)


__all__ = ["SafeVOIPolicy", "TaskCandidate", "TaskDecision", "rank_tasks"]
