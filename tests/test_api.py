from fastapi.testclient import TestClient

from t3c2_path.api import app
from t3c2_path.demo import demo_request


client = TestClient(app)


def test_health_endpoint_reports_research_boundary() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["data_mode"] == "synthetic_only"


def test_decision_endpoint_returns_a_structured_auditable_package() -> None:
    response = client.post(
        "/v1/decisions/evaluate", json=demo_request().model_dump(mode="json")
    )
    assert response.status_code == 200
    body = response.json()
    assert body["action"] == "PUBLISH"
    assert body["auditLog"]["inputHash"].startswith("sha256:")
    assert body["profiles"]


def test_validation_errors_have_one_machine_readable_shape() -> None:
    payload = demo_request().model_dump(mode="json")
    payload["unexpectedField"] = "reject me"
    response = client.post("/v1/decisions/evaluate", json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
