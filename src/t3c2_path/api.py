"""Optional FastAPI adapter for the reference orchestrator."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from t3c2_path.application import DecisionRequest, GrowthOpsOrchestrator
from t3c2_path.audit import AppendOnlyAuditStore

app = FastAPI(
    title="T3-C2 Path GrowthOps",
    version="0.1.0",
    description="Synthetic-only research API; not a production student decision service.",
)
_audit_store = AppendOnlyAuditStore()
_orchestrator = GrowthOpsOrchestrator(_audit_store)


def _camel_case(name: str) -> str:
    head, *tail = name.split("_")
    return head + "".join(item.capitalize() for item in tail)


def _camelize(value: Any) -> Any:
    if isinstance(value, dict):
        return {_camel_case(str(key)): _camelize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_camelize(item) for item in value]
    return value


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_request: Any, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Invalid request",
                "details": jsonable_encoder(exc.errors()),
            }
        },
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": "0.1.0", "data_mode": "synthetic_only"}


@app.post("/v1/decisions/evaluate")
def evaluate_decision(request: DecisionRequest) -> JSONResponse:
    package = _orchestrator.evaluate(request)
    content = _camelize(package.model_dump(mode="json"))
    return JSONResponse(content=content)


__all__ = ["app"]
