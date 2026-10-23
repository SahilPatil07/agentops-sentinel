from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from agentic_worker.domain.errors import WorkerError
from agentic_worker.domain.models import IncidentCreate, RunStatus, TraceEvent
from agentic_worker.persistence.store import RunRow, Store


def test_interrupted_run_and_trace_survive_restart(tmp_path: Path) -> None:
    path = str(tmp_path / "runs.sqlite3")
    store = Store(path)
    store.initialize()
    incident = store.create_incident(
        IncidentCreate(
            title="Failure",
            description="Upload failed",
            service="document-ingestion",
            severity="high",
        )
    )
    run = store.create_run(incident.incident_id, 8)
    store.append_trace(
        TraceEvent(
            run_id=run.run_id,
            sequence=1,
            timestamp=datetime.now(UTC),
            stage="run",
            event="run_started",
        )
    )
    store.close()
    restarted = Store(path)
    try:
        restarted.initialize()
        recovered = restarted.get_run(run.run_id)
        assert recovered.status == RunStatus.FAILED
        assert recovered.error_code == "interrupted"
        assert recovered.finished_at is not None
        assert [event.sequence for event in restarted.get_trace(run.run_id)] == [1, 2]
        assert restarted.get_trace(run.run_id)[-1].error_code == "interrupted"
        with pytest.raises(WorkerError):
            restarted.get_report(run.run_id)
        restarted.initialize()
        assert len(restarted.get_trace(run.run_id)) == 2
    finally:
        restarted.close()


def test_database_rejects_orphaned_runs() -> None:
    store = Store(":memory:")
    try:
        store.initialize()
        with pytest.raises(IntegrityError), Session(store.engine) as session, session.begin():
            session.add(
                RunRow(
                    run_id="run_orphan", incident_id="inc_missing", status="running", payload="{}"
                )
            )
    finally:
        store.close()
