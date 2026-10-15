import asyncio
from uuid import UUID

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from starlette.types import Message, Receive, Scope, Send

from agentic_worker.api.middleware import RequestBoundaryMiddleware
from agentic_worker.config import Settings
from agentic_worker.domain.errors import ErrorCode, WorkerError
from agentic_worker.domain.models import IncidentCreate
from agentic_worker.main import create_app


def test_health_during_lifespan() -> None:
    application = create_app(Settings(_env_file=None))
    with TestClient(application) as client:
        for endpoint, expected in [("live", "alive"), ("ready", "ready")]:
            response = client.get(f"/api/v1/health/{endpoint}")
            assert response.status_code == 200
            assert response.json() == {"status": expected}


def test_readiness_outside_lifespan() -> None:
    application = create_app(Settings(_env_file=None))
    client = TestClient(application)
    assert client.get("/api/v1/health/ready").status_code == 503
    with client:
        assert client.get("/api/v1/health/ready").status_code == 200
    assert client.get("/api/v1/health/ready").status_code == 503


def test_openapi_health_contracts() -> None:
    with TestClient(create_app(Settings(_env_file=None))) as client:
        schema = client.get("/openapi.json").json()
    for endpoint in ("live", "ready"):
        operation = schema["paths"][f"/api/v1/health/{endpoint}"]["get"]
        assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
            "$ref": "#/components/schemas/HealthResponse"
        }


@pytest.fixture(name="error_app")
def make_error_app() -> FastAPI:
    application = create_app(Settings(_env_file=None, max_request_bytes=1024))

    @application.post("/contract")
    async def contract(incident: IncidentCreate) -> IncidentCreate:
        return incident

    @application.get("/failure")
    async def failure() -> None:
        raise RuntimeError("sensitive-internal-value")

    @application.get("/http-error")
    async def http_error() -> None:
        raise HTTPException(status_code=403, detail="sensitive-internal-value")

    @application.get("/conflict")
    async def conflict() -> None:
        raise WorkerError(ErrorCode.INVALID_STATE)

    return application


@pytest.mark.parametrize(
    ("endpoint", "status", "code"),
    [
        ("/unknown", 404, "not_found"),
        ("/failure", 500, "internal_error"),
        ("/http-error", 403, "http_error"),
        ("/conflict", 409, "invalid_state"),
    ],
)
def test_sanitized_errors(error_app: FastAPI, endpoint: str, status: int, code: str) -> None:
    with TestClient(error_app) as client:
        response = client.get(endpoint, headers={"X-Request-ID": "untrusted-id"})
    assert response.status_code == status
    assert response.json()["code"] == code
    assert str(UUID(response.headers["x-request-id"])) == response.json()["request_id"]
    assert "sensitive-internal-value" not in response.text


def test_validation_does_not_echo_input(error_app: FastAPI) -> None:
    with TestClient(error_app) as client:
        response = client.post("/contract", json={"title": "sensitive-internal-value"})
        malformed = client.post("/contract", content=b'{"secret": sensitive-internal-value}')
    for result in (response, malformed):
        assert result.status_code == 422
        assert result.json()["code"] == "invalid_request"
        assert "sensitive-internal-value" not in result.text


def test_valid_request_body_is_preserved(error_app: FastAPI) -> None:
    payload = {
        "title": "Ingestion errors",
        "description": "Uploads fail.",
        "service": "document-ingestion",
        "severity": "high",
    }
    with TestClient(error_app) as client:
        response = client.post("/contract", json=payload)
    assert response.status_code == 200
    assert response.json()["title"] == payload["title"]


def test_body_limit_with_and_without_content_length(error_app: FastAPI) -> None:
    with TestClient(error_app) as client:
        declared = client.post("/contract", content=b"x" * 1025)
        chunked = client.post("/contract", content=iter([b"x" * 600, b"x" * 600]))
        dishonest = client.post("/contract", content=b"x" * 1025, headers={"Content-Length": "1"})
    for result in (declared, chunked, dishonest):
        assert result.status_code == 413
        assert result.json()["code"] == "request_too_large"
        assert result.json()["request_id"] == result.headers["x-request-id"]


def test_method_not_allowed_preserves_allow_header() -> None:
    with TestClient(create_app(Settings(_env_file=None))) as client:
        response = client.post("/api/v1/health/live")
    assert response.status_code == 405
    assert response.headers["allow"] == "GET"


def test_streamed_body_rejected_before_downstream_execution() -> None:
    messages = iter(
        [
            {"type": "http.request", "body": b"x" * 600, "more_body": True},
            {"type": "http.request", "body": b"x" * 600, "more_body": True},
        ]
    )
    sent: list[Message] = []

    async def receive() -> Message:
        return next(messages)

    async def send(message: Message) -> None:
        sent.append(message)

    async def downstream(scope: Scope, receive: Receive, send: Send) -> None:
        pytest.fail("Oversized input reached application code")

    middleware = RequestBoundaryMiddleware(
        downstream, Settings(_env_file=None, max_request_bytes=1024)
    )
    asyncio.run(middleware({"type": "http", "method": "POST", "headers": []}, receive, send))
    assert sent[0]["status"] == 413
