import io
import json
import logging
from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient

from agentic_worker.config import Settings
from agentic_worker.main import create_app
from agentic_worker.observability.logging import JsonFormatter


def test_formatter_excludes_arbitrary_messages_and_extras() -> None:
    record = logging.LogRecord("worker", logging.ERROR, "", 1, "sensitive-value", (), None)
    record.__dict__["authorization"] = "sensitive-value"
    rendered = JsonFormatter().format(record)
    assert "sensitive-value" not in rendered
    assert json.loads(rendered)["event"] == "application_event"


def test_request_logs_never_include_untrusted_content() -> None:
    application: FastAPI = create_app(Settings(_env_file=None))

    @application.get("/failure")
    async def failure() -> None:
        raise RuntimeError("sensitive-value")

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("agentic_worker")
    logger.addHandler(handler)
    try:
        with TestClient(application) as client:
            response = client.post(
                "/sensitive-value?token=sensitive-value",
                headers={"Authorization": "sensitive-value", "X-Request-ID": "sensitive-value"},
                content="sensitive-value",
            )
            failure_response = client.get("/failure")
    finally:
        logger.removeHandler(handler)
        handler.close()

    output = stream.getvalue()
    assert "sensitive-value" not in output
    assert "Traceback" not in output
    events = [json.loads(line) for line in output.splitlines()]
    assert len(events) == 2
    assert events[0]["route"] == "unmatched"
    assert events[0]["request_id"] == response.headers["x-request-id"]
    assert str(UUID(events[1]["request_id"])) == failure_response.headers["x-request-id"]
    assert events[1]["event"] == "request_failed"
    assert events[1]["status_code"] == 500
    assert events[1]["duration_ms"] >= 0
