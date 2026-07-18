import json
from pathlib import Path

from t3c2_path.research import (
    export_validation_bundle,
    generate_known_truth_cohort,
    run_known_truth_validation,
)

ROOT = Path(__file__).resolve().parents[1]


def test_synthetic_generator_is_reproducible_and_explicitly_marked() -> None:
    first = generate_known_truth_cohort(n=100, seed=20260719)
    second = generate_known_truth_cohort(n=100, seed=20260719)
    assert first == second
    assert all(item.is_synthetic for item in first)
    assert all(item.subject_id.startswith("SYN-") for item in first)


def test_aipw_is_checked_against_known_truth_and_naive_bias() -> None:
    report = run_known_truth_validation(n=1_200, seed=20260719)
    assert report.research_boundary == "synthetic_only_not_real_world_evidence"
    assert abs(report.aipw_estimate - report.true_ate) < 0.5
    assert abs(report.aipw_estimate - report.true_ate) < abs(
        report.naive_difference - report.true_ate
    )
    assert report.aipw_interval_low <= report.true_ate <= report.aipw_interval_high


def test_validation_report_keeps_observed_expected_and_claim_boundary() -> None:
    report = run_known_truth_validation(n=400, seed=7)
    dumped = report.model_dump()
    assert dumped["observed"]["analyzed_n"] > 0
    assert dumped["expected_property"]["known_truth_available"] is True
    assert "真实学生" in dumped["claim_boundary"]["prohibited_claim_zh"]


def test_red_team_registry_has_unique_executable_expectations() -> None:
    cases = json.loads((ROOT / "research" / "red_team_cases.json").read_text(encoding="utf-8"))
    assert len(cases) >= 12
    assert len({item["case_id"] for item in cases}) == len(cases)
    assert all(item["expected_action"] for item in cases)
    assert all(item["forbidden_output"] for item in cases)


def test_validation_bundle_exports_data_report_and_manifest(tmp_path: Path) -> None:
    manifest = export_validation_bundle(tmp_path, n=100, seed=7)
    assert manifest["rows"] == 100
    assert (tmp_path / "synthetic_known_truth.csv").exists()
    assert (tmp_path / "validation_report.json").exists()
    assert (tmp_path / "manifest.json").exists()
    report = json.loads((tmp_path / "validation_report.json").read_text(encoding="utf-8"))
    assert report["research_boundary"] == "synthetic_only_not_real_world_evidence"
