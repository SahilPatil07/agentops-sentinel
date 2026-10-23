from pathlib import Path

from fastapi.testclient import TestClient

from agentic_worker.config import Settings
from agentic_worker.main import create_app

INCIDENT = {
    "title": "Document ingestion returns 502",
    "description": "Upload completes but extraction fails with connection errors.",
    "service": "document-ingestion",
    "severity": "high",
    "environment": "demo",
    "evidence": ["request-id-123"],
}


def create_proposed_action(client: TestClient) -> tuple[str, str, str]:
    incident = client.post("/api/v1/incidents", json=INCIDENT).json()
    run = client.post(f"/api/v1/incidents/{incident['incident_id']}/runs", json={}).json()
    report = client.get(f"/api/v1/runs/{run['run_id']}/report").json()
    action = report["recommended_actions"][0]
    return run["run_id"], action["action_id"], action["plan_version"]


def test_simulated_action_requires_current_approval() -> None:
    with TestClient(create_app(Settings(_env_file=None))) as client:
        run_id, action_id, plan_version = create_proposed_action(client)
        path = f"/api/v1/runs/{run_id}/actions/{action_id}"

        missing = client.post(f"{path}/execute", json={"plan_version": plan_version})
        assert missing.status_code == 403
        assert missing.json()["code"] == "policy_blocked"

        rejected = client.post(
            f"{path}/reject",
            json={"reviewer": "demo-reviewer", "plan_version": plan_version},
        )
        assert rejected.status_code == 200
        assert rejected.json()["decision"] == "rejected"
        blocked = client.post(f"{path}/execute", json={"plan_version": plan_version})
        assert blocked.status_code == 403

        approved = client.post(
            f"{path}/approve",
            json={"reviewer": "demo-reviewer", "plan_version": plan_version},
        )
        assert approved.status_code == 200
        stale = client.post(f"{path}/execute", json={"plan_version": "0" * 64})
        assert stale.status_code == 409

        executed = client.post(f"{path}/execute", json={"plan_version": plan_version})
        assert executed.status_code == 200
        assert executed.json()["status"] == "simulated"
        assert executed.json()["simulated"] is True

        repeated = client.post(f"{path}/execute", json={"plan_version": plan_version})
        assert repeated.status_code == 200
        assert repeated.json() == executed.json()


def test_approval_and_simulated_outcome_survive_restart(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, database_path=str(tmp_path / "actions.sqlite3"))
    with TestClient(create_app(settings)) as client:
        run_id, action_id, plan_version = create_proposed_action(client)
        path = f"/api/v1/runs/{run_id}/actions/{action_id}"
        decision = client.post(
            f"{path}/approve",
            json={"reviewer": "demo-reviewer", "plan_version": plan_version},
        )
        assert decision.status_code == 200
        outcome = client.post(f"{path}/execute", json={"plan_version": plan_version})
        assert outcome.status_code == 200

    with TestClient(create_app(settings)) as restarted:
        repeated = restarted.post(f"{path}/execute", json={"plan_version": plan_version})
        assert repeated.status_code == 200
        assert repeated.json() == outcome.json()
