"""Open synthetic generator and known-truth validation utilities.

These functions test estimator mechanics under an explicitly known data
generating process.  They do not simulate the full complexity of real students
and cannot establish external validity or service effectiveness.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import random
from datetime import UTC, datetime
from pathlib import Path

from pydantic import Field

from t3c2_path.algorithms.service_effect import (
    CausalObservation,
    TargetTrialSpec,
    estimate_aipw,
)
from t3c2_path.audit import canonical_hash
from t3c2_path.domain import FrozenModel

VALIDATION_TIME = datetime(2026, 7, 19, 8, 0, tzinfo=UTC)
RESEARCH_BOUNDARY = "synthetic_only_not_real_world_evidence"


class SyntheticCohortRow(FrozenModel):
    subject_id: str
    baseline_readiness: float
    motivation: float = Field(ge=0, le=1)
    resource_access: float = Field(ge=0, le=1)
    propensity: float = Field(gt=0, lt=1)
    assigned: bool
    received_service: bool
    expected_y0: float
    expected_y1: float
    y0: float
    y1: float
    observed_outcome: float
    true_effect: float
    observed: bool
    is_synthetic: bool = True


class ValidationReport(FrozenModel):
    seed: int
    generated_n: int = Field(gt=0)
    analyzed_n: int = Field(gt=0)
    true_ate: float
    naive_difference: float
    aipw_estimate: float
    aipw_interval_low: float
    aipw_interval_high: float
    naive_absolute_bias: float = Field(ge=0)
    aipw_absolute_bias: float = Field(ge=0)
    propensity_min: float = Field(gt=0, lt=1)
    propensity_max: float = Field(gt=0, lt=1)
    dataset_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    observed: dict[str, int | float]
    expected_property: dict[str, bool | str]
    claim_boundary: dict[str, str]
    research_boundary: str


def _logistic(value: float) -> float:
    return 1.0 / (1.0 + math.exp(-value))


def generate_known_truth_cohort(
    *, n: int = 1_200, seed: int = 20260719
) -> tuple[SyntheticCohortRow, ...]:
    if n < 20:
        raise ValueError("n must be at least 20 for the validation exercise")
    rng = random.Random(seed)
    rows: list[SyntheticCohortRow] = []
    for index in range(n):
        baseline = rng.uniform(35.0, 75.0)
        motivation = rng.random()
        resources = rng.random()
        logit = -1.3 + 0.045 * (baseline - 50.0) + 1.5 * motivation + 0.9 * resources
        propensity = min(0.92, max(0.08, _logistic(logit)))
        assigned = rng.random() < propensity
        received = assigned if rng.random() >= 0.10 else not assigned
        true_effect = 2.0 + 1.5 * (1.0 - resources) + 0.5 * motivation
        expected_y0 = 18.0 + 0.65 * baseline + 8.0 * motivation + 4.0 * resources
        expected_y1 = expected_y0 + true_effect
        shared_noise = rng.gauss(0.0, 4.0)
        y0 = expected_y0 + shared_noise
        y1 = expected_y1 + shared_noise
        outcome = y1 if assigned else y0
        observed = rng.random() >= 0.05
        rows.append(
            SyntheticCohortRow(
                subject_id=f"SYN-{index + 1:05d}",
                baseline_readiness=baseline,
                motivation=motivation,
                resource_access=resources,
                propensity=propensity,
                assigned=assigned,
                received_service=received,
                expected_y0=expected_y0,
                expected_y1=expected_y1,
                y0=y0,
                y1=y1,
                observed_outcome=outcome,
                true_effect=true_effect,
                observed=observed,
            )
        )
    return tuple(rows)


def run_known_truth_validation(
    *, n: int = 1_200, seed: int = 20260719
) -> ValidationReport:
    cohort = generate_known_truth_cohort(n=n, seed=seed)
    records = tuple(
        CausalObservation(
            subject_id=row.subject_id,
            assigned=row.assigned,
            received_service=row.received_service,
            outcome=row.observed_outcome,
            propensity=row.propensity,
            expected_outcome_no_service=row.expected_y0,
            expected_outcome_service=row.expected_y1,
            strategy_version="synthetic-service/0.1.0",
            eligible=True,
            observed=row.observed,
            is_synthetic=True,
        )
        for row in cohort
    )
    trial = TargetTrialSpec(
        trial_id="known-truth-synthetic-cohort",
        population_definition="all generated synthetic records",
        strategy_version="synthetic-service/0.1.0",
        time_zero=VALIDATION_TIME,
        estimand="ATE",
        has_comparator=True,
        stable_intervention=True,
        minimum_overlap=0.05,
        is_synthetic=True,
    )
    aipw = estimate_aipw(trial, records, created_at=VALIDATION_TIME)
    if aipw.report is None:
        raise RuntimeError(f"known-truth validation failed: {aipw.reason_codes}")
    analyzed = [row for row in cohort if row.observed]
    treated = [row.observed_outcome for row in analyzed if row.assigned]
    control = [row.observed_outcome for row in analyzed if not row.assigned]
    naive = sum(treated) / len(treated) - sum(control) / len(control)
    true_ate = sum(row.true_effect for row in cohort) / len(cohort)
    dataset_hash = canonical_hash([row.model_dump(mode="json") for row in cohort])
    return ValidationReport(
        seed=seed,
        generated_n=len(cohort),
        analyzed_n=len(analyzed),
        true_ate=true_ate,
        naive_difference=naive,
        aipw_estimate=aipw.report.estimate,
        aipw_interval_low=aipw.report.interval_low,
        aipw_interval_high=aipw.report.interval_high,
        naive_absolute_bias=abs(naive - true_ate),
        aipw_absolute_bias=abs(aipw.report.estimate - true_ate),
        propensity_min=min(row.propensity for row in analyzed),
        propensity_max=max(row.propensity for row in analyzed),
        dataset_hash=dataset_hash,
        observed={
            "generated_n": len(cohort),
            "analyzed_n": len(analyzed),
            "assigned_n": sum(row.assigned for row in analyzed),
            "crossover_n": sum(row.assigned != row.received_service for row in analyzed),
            "aipw_estimate": aipw.report.estimate,
        },
        expected_property={
            "known_truth_available": True,
            "aipw_closer_than_naive": abs(aipw.report.estimate - true_ate)
            < abs(naive - true_ate),
            "truth_inside_aipw_interval": aipw.report.interval_low
            <= true_ate
            <= aipw.report.interval_high,
        },
        claim_boundary={
            "allowed_claim_en": (
                "The implementation recovered the injected synthetic effect "
                "under this generator."
            ),
            "prohibited_claim_zh": "不得据此宣称算法已对真实学生有效或华图服务产生真实因果效果。",
        },
        research_boundary=RESEARCH_BOUNDARY,
    )


def export_validation_bundle(
    output_dir: Path, *, n: int = 1_200, seed: int = 20260719
) -> dict[str, object]:
    """Export a deterministic CSV, validation report and integrity manifest."""

    output_dir.mkdir(parents=True, exist_ok=True)
    cohort = generate_known_truth_cohort(n=n, seed=seed)
    report = run_known_truth_validation(n=n, seed=seed)
    csv_path = output_dir / "synthetic_known_truth.csv"
    report_path = output_dir / "validation_report.json"
    manifest_path = output_dir / "manifest.json"

    fieldnames = list(cohort[0].model_dump(mode="json"))
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(item.model_dump(mode="json") for item in cohort)
    report_path.write_text(
        json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )

    def sha256(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    manifest: dict[str, object] = {
        "generator": "t3c2_path.research.export_validation_bundle",
        "seed": seed,
        "rows": n,
        "dataset_hash": report.dataset_hash,
        "research_boundary": RESEARCH_BOUNDARY,
        "files": {
            csv_path.name: {
                "sha256": sha256(csv_path),
                "bytes": csv_path.stat().st_size,
            },
            report_path.name: {
                "sha256": sha256(report_path),
                "bytes": report_path.stat().st_size,
            },
        },
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


__all__ = [
    "RESEARCH_BOUNDARY",
    "SyntheticCohortRow",
    "ValidationReport",
    "export_validation_bundle",
    "generate_known_truth_cohort",
    "run_known_truth_validation",
]
