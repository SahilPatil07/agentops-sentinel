from pathlib import Path
from typing import cast

import pytest
from fastapi.testclient import TestClient

from agentic_worker.config import Settings
from agentic_worker.main import create_app
from agentic_worker.persistence.store import Base, Store

INCIDENT = {
    "title": "Document ingestion returns 502",
    "description": "Upload completes but extraction fails with connection errors.",
    "service": "document-ingestion",
    "severity": "high",
    "environment": "demo",
    "evidence": ["request-id-123"],
}


def test_incident_survives_restart(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, database_path=str(tmp_path / "incidents.sqlite3"))
    with TestClient(create_app(settings)) as client:
        response = client.post("/api/v1/incidents", json=INCIDENT)
        assert response.status_code == 201
        record = response.json()
        assert record["incident_id"].startswith("inc_")
        assert record["status"] == "created"
    with TestClient(create_app(settings)) as restarted:
        response = restarted.get(f"/api/v1/incidents/{record['incident_id']}")
        assert response.status_code == 200
        assert response.json() == record
        assert restarted.get("/api/v1/health/ready").status_code == 200


def test_incident_not_found_and_validation() -> None:
    with TestClient(create_app(Settings(_env_file=None))) as client:
        assert client.get("/api/v1/incidents/missing").status_code == 404
        assert client.post("/api/v1/incidents", json={}).status_code == 422
        assert (
            client.post("/api/v1/incidents", json={**INCIDENT, "execute": True}).status_code == 422
        )


def test_investigation_report_and_trace_survive_restart(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, database_path=str(tmp_path / "investigation.sqlite3"))
    with TestClient(create_app(settings)) as client:
        incident = client.post("/api/v1/incidents", json=INCIDENT).json()
        response = client.post(f"/api/v1/incidents/{incident['incident_id']}/runs", json={})
        assert response.status_code == 200
        run = response.json()
        assert run["status"] == "succeeded", run
        assert run["tool_calls"] == 4
        assert run["steps"] == 5
        assert run["provider_name"] == "deterministic_mock"
        path = f"/api/v1/runs/{run['run_id']}"
        report = client.get(f"{path}/report").json()
        trace = client.get(f"{path}/trace").json()
        collected = {item["source_id"] for event in trace for item in event["observations"]}
        assert collected == {item["source_id"] for item in report["source_citations"]}
        assert len(collected) == 4
        knowledge = {item["chunk_id"] for event in trace for item in event["knowledge_citations"]}
        assert knowledge == {item["chunk_id"] for item in report["knowledge_citations"]}
        assert knowledge
        for citation in report["knowledge_citations"]:
            chunk = client.get(f"/api/v1/knowledge/chunks/{citation['chunk_id']}")
            assert chunk.status_code == 200
            assert chunk.json()["text"] == citation["excerpt"]
        assert all(action["approval_required"] for action in report["recommended_actions"])
        assert all(
            action["execution_status"] == "not_executed" for action in report["recommended_actions"]
        )
        assert [event["sequence"] for event in trace] == list(range(1, len(trace) + 1))
        assert trace[-1]["event"] == "run_completed"
        documents = client.get("/api/v1/knowledge/documents").json()
        assert len(documents) == 8
    with TestClient(create_app(settings)) as restarted:
        assert restarted.get(path).json() == run
        assert restarted.get(f"{path}/report").json() == report
        assert restarted.get(f"{path}/trace").json() == trace
        assert restarted.get(f"{path}/trace?offset=1&limit=2").json() == trace[1:3]
        assert restarted.get("/api/v1/knowledge/documents").json() == documents


def test_unknown_service_requests_evidence() -> None:
    with TestClient(create_app(Settings(_env_file=None))) as client:
        incident = client.post("/api/v1/incidents", json={**INCIDENT, "service": "unknown"}).json()
        run = client.post(f"/api/v1/incidents/{incident['incident_id']}/runs", json={}).json()
        assert run["status"] == "needs_input"
        report = client.get(f"/api/v1/runs/{run['run_id']}/report").json()
        assert report["source_citations"] == []
        assert report["hypotheses"] == []
        assert report["recommended_actions"] == []
        assert report["missing_information"]


def test_conflicting_retrieval_abstains() -> None:
    settings = Settings(_env_file=None, retrieval_top_k=4, retrieval_min_score=0)
    with TestClient(create_app(settings)) as client:
        incident = client.post("/api/v1/incidents", json=INCIDENT).json()
        run = client.post(f"/api/v1/incidents/{incident['incident_id']}/runs", json={}).json()
        assert run["status"] == "needs_input"
        report = client.get(f"/api/v1/runs/{run['run_id']}/report").json()
        assert report["hypotheses"] == []
        assert report["recommended_actions"] == []
        assert "conflict" in report["summary"].lower()
        assert {citation["stance"] for citation in report["knowledge_citations"]} >= {
            "supports",
            "contradicts",
        }


def test_invalid_run_requests_and_missing_resources() -> None:
    with TestClient(create_app(Settings(_env_file=None))) as client:
        assert client.post("/api/v1/incidents/missing/runs", json={}).status_code == 404
        for suffix in ("", "/report", "/trace"):
            assert client.get(f"/api/v1/runs/missing{suffix}").status_code == 404
        incident = client.post("/api/v1/incidents", json=INCIDENT).json()
        path = f"/api/v1/incidents/{incident['incident_id']}/runs"
        for payload in (
            {"mode": "execute"},
            {"max_tool_calls": 0},
            {"max_tool_calls": 17},
            {"max_tool_calls": "8"},
            {"approval": True},
        ):
            assert client.post(path, json=payload).status_code == 422
        run = client.post(path, json={"max_tool_calls": 1}).json()
        assert run["status"] == "blocked"
        assert run["tool_calls"] == 1
        assert client.get(f"/api/v1/runs/{run['run_id']}/trace?limit=101").status_code == 422


@pytest.mark.parametrize("table_name", ["incidents", "runs", "trace_events"])
def test_liveness_stays_up_when_database_is_not_ready(table_name: str) -> None:
    application = create_app(Settings(_env_file=None))
    store = cast(Store, application.state.store)
    with TestClient(application) as client:
        with store.engine.begin() as connection:
            Base.metadata.tables[table_name].drop(connection)
        assert client.get("/api/v1/health/live").status_code == 200
        assert client.get("/api/v1/health/ready").status_code == 503


def test_readiness_checks_vector_index(monkeypatch: pytest.MonkeyPatch) -> None:
    application = create_app(Settings(_env_file=None))
    with TestClient(application) as client:
        knowledge = application.state.knowledge
        monkeypatch.setattr(knowledge, "ready", lambda: False)
        assert client.get("/api/v1/health/live").status_code == 200
        assert client.get("/api/v1/health/ready").status_code == 503
