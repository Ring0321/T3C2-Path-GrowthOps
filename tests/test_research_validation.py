import json
from pathlib import Path

from t3c2_path.red_team import run_red_team_suite
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
    assert all(
        len(str(value).partition(".")[2]) <= 10
        for item in first
        for value in (
            item.baseline_readiness,
            item.motivation,
            item.resource_access,
            item.propensity,
            item.expected_y0,
            item.expected_y1,
            item.y0,
            item.y1,
        )
    )


def test_aipw_is_checked_against_known_truth_and_naive_bias() -> None:
    report = run_known_truth_validation(n=1_200, seed=20260719)
    assert report.research_boundary == "synthetic_only_not_real_world_evidence"
    assert (
        report.dataset_hash
        == "sha256:c53c305540b1292551ccf136c9834b90b29a3468656386528755add05d33eb99"
    )
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
    assert [item["case_id"] for item in cases] == [f"R{i:02d}" for i in range(1, 13)]
    assert all(item["expected_behavior"] for item in cases)
    assert all(item["forbidden_behavior"] for item in cases)
    assert all(item["executable_reference"].startswith("t3c2_path.red_team:") for item in cases)


def test_validation_bundle_exports_data_report_and_manifest(tmp_path: Path) -> None:
    manifest = export_validation_bundle(tmp_path, n=100, seed=7)
    assert manifest["rows"] == 100
    assert (tmp_path / "synthetic_known_truth.csv").exists()
    assert (tmp_path / "validation_report.json").exists()
    assert (tmp_path / "manifest.json").exists()
    report = json.loads((tmp_path / "validation_report.json").read_text(encoding="utf-8"))
    assert report["research_boundary"] == "synthetic_only_not_real_world_evidence"


def test_submission_release_maps_every_generator_and_freezes_one_canonical_role() -> None:
    manifest = json.loads(
        (ROOT / "research" / "submission_release_manifest.json").read_text(encoding="utf-8")
    )
    committed = json.loads(
        (ROOT / "research" / "generated" / "validation_report.json").read_text(
            encoding="utf-8"
        )
    )
    assert manifest["release_version"] == "1.1.0"
    assert manifest["canonical_reproducibility_generator"] == "open-source-reference/0.2.0"
    reference = manifest["generators"]["open-source-reference/0.2.0"]
    assert reference["dataset_hash"] == committed["dataset_hash"]
    assert reference["aipw_estimate"] == committed["aipw_estimate"]
    fixture = manifest["generators"]["document-design-fixture/1.0.0"]
    assert fixture["aipw_estimate"] != reference["aipw_estimate"]
    assert manifest["comparison_rule"] == "DO_NOT_COMPARE_NUMERIC_ESTIMATES_ACROSS_DGP"


def test_all_twelve_submission_red_team_cases_are_executable_and_pass() -> None:
    results = run_red_team_suite()
    assert [item.case_id for item in results] == [f"R{i:02d}" for i in range(1, 13)]
    assert all(item.status == "PASS" for item in results)
    assert all(item.test_reference and item.actual_evidence for item in results)
