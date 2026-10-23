import pytest
from pydantic import ValidationError

from agentic_worker.domain.models import IncidentCreate, RecommendedAction


def valid_incident() -> dict[str, object]:
    return {
        "title": " Ingestion errors ",
        "description": "Uploads fail after completion.",
        "service": "document-ingestion",
        "severity": "high",
    }


def test_incident_contract() -> None:
    incident = IncidentCreate.model_validate(valid_incident())
    assert incident.title == "Ingestion errors"
    assert incident.environment == "demo"
    assert incident.evidence == []
    assert IncidentCreate.model_validate_json(incident.model_dump_json()) == incident


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("title", "   "),
        ("title", "x" * 201),
        ("title", 123),
        ("description", "x" * 10_001),
        ("description", ""),
        ("service", "../other"),
        ("severity", "urgent"),
        ("environment", "production"),
        ("evidence", ["reference"] * 21),
        ("evidence", ["x" * 501]),
        ("evidence", [""]),
        ("evidence", [123]),
        ("execute_shell", True),
    ],
)
def test_invalid_incident(field: str, value: object) -> None:
    payload = {**valid_incident(), field: value}
    with pytest.raises(ValidationError):
        IncidentCreate.model_validate(payload)


def test_action_plan_version_is_content_bound() -> None:
    payload = {
        "action_id": "review-host",
        "title": "Review host configuration",
        "risk": "medium",
        "preconditions": ["Confirm the intended host."],
        "expected_result": "Connectivity is restored in the simulation.",
        "verification": ["Check simulated connectivity."],
        "rollback": "Restore the previous simulated value.",
    }
    action = RecommendedAction.model_validate(payload)
    assert RecommendedAction.model_validate_json(action.model_dump_json()) == action
    with pytest.raises(ValidationError):
        RecommendedAction.model_validate({**payload, "plan_version": "0" * 64})
