import json
from pathlib import Path

from t3c2_path.cli import main, render_demo


def test_render_demo_returns_reproducible_synthetic_result() -> None:
    first = render_demo()
    second = render_demo()
    assert first == second
    assert first["action"] == "PUBLISH"
    assert first["audit_log"]["is_synthetic"] is True


def test_cli_writes_a_json_artifact_with_research_boundary(tmp_path: Path) -> None:
    output = tmp_path / "demo-result.json"
    exit_code = main(["demo", "--output", str(output)])
    assert exit_code == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["action"] == "PUBLISH"
    assert payload["research_boundary"] == "synthetic_only_not_real_world_evidence"
