"""Deterministic synthetic request used by documentation, CLI and API tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from t3c2_path.algorithms.path_twin import PathDefinition
from t3c2_path.algorithms.safe_voi import TaskCandidate
from t3c2_path.application import DecisionRequest, GateMetrics, PriorState
from t3c2_path.domain import (
    ConsentRecord,
    DecisionPurpose,
    EvidenceRecord,
    EvidenceStatus,
    SourceKind,
)


DEMO_TIME = datetime(2026, 7, 19, 8, 0, tzinfo=UTC)


def _evidence(evidence_id: str, dimension: str, value: float) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=evidence_id,
        subject_id="synthetic-student-001",
        dimension=dimension,
        observed_value=value,
        base_sd=6.0,
        reliability=0.9,
        observed_at=DEMO_TIME - timedelta(days=2),
        recorded_at=DEMO_TIME,
        source_kind=SourceKind.WORK_SAMPLE,
        context="structured_task",
        authorization_id="consent-001",
        status=EvidenceStatus.ACTIVE,
        is_synthetic=True,
    )


def demo_request() -> DecisionRequest:
    consent = ConsentRecord(
        consent_id="consent-001",
        subject_id="synthetic-student-001",
        purposes=frozenset({DecisionPurpose.FORMATIVE_PLANNING}),
        valid_from=DEMO_TIME - timedelta(days=1),
        valid_to=DEMO_TIME + timedelta(days=30),
        is_synthetic=True,
    )
    return DecisionRequest(
        decision_id="decision-synthetic-demo",
        subject_id="synthetic-student-001",
        purpose=DecisionPurpose.FORMATIVE_PLANNING,
        decision_time=DEMO_TIME,
        consent=consent,
        evidence_records=(
            _evidence("e-analysis", "analysis", 65),
            _evidence("e-communication", "communication", 63),
        ),
        priors={
            "analysis": PriorState(mean=50, sd=10, half_life_days=56),
            "communication": PriorState(mean=50, sd=10, half_life_days=56),
        },
        path_definitions=(
            PathDefinition(
                path_id="market-employment",
                requirements={"analysis": 60.0, "communication": 60.0},
                weights={"analysis": 0.5, "communication": 0.5},
                weekly_workload_hours=10,
                transferability=85,
                window_days=90,
                critical_margin=15,
            ),
        ),
        knowledge_rules=(),
        task_candidates=(
            TaskCandidate(
                task_id="portfolio-experiment",
                expected_growth=8,
                information_gain=8,
                transferability=9,
                window_rescue=6,
                burden=3,
                risk=1,
                estimated_hours=2,
                monetary_cost=0,
                consent_valid=True,
                rules_valid=True,
                is_reversible=True,
                is_high_stakes=False,
                is_paid_service=False,
            ),
        ),
        gate_metrics=GateMetrics(
            expected_evidence_count=2,
            calibration_ece=0.04,
            fairness_gap=0.05,
        ),
        model_versions={
            "evidence": "evidence-state/0.1.0",
            "path": "path-twin/0.1.0",
            "task": "safe-voi/0.1.0",
            "gate": "safety-gate/0.1.0",
        },
        knowledge_version="synthetic-rules/0.1.0",
        seed=7,
        simulation_draws=300,
        is_synthetic=True,
    )


__all__ = ["DEMO_TIME", "demo_request"]
