import sqlite3
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import URL, ForeignKey, String, Text, create_engine, select
from sqlalchemy.event import listen
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from sqlalchemy.pool import ConnectionPoolEntry, StaticPool

from agentic_worker.domain.errors import ErrorCode, WorkerError
from agentic_worker.domain.models import (
    IncidentCreate,
    IncidentRecord,
    IncidentReport,
    RunRecord,
    RunStatus,
    TraceEvent,
)


class Base(DeclarativeBase):
    pass


class IncidentRow(Base):
    __tablename__ = "incidents"

    incident_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    payload: Mapped[str] = mapped_column(Text)


class RunRow(Base):
    __tablename__ = "runs"

    run_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.incident_id"), index=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    payload: Mapped[str] = mapped_column(Text)
    report: Mapped[str | None] = mapped_column(Text, nullable=True)


class TraceRow(Base):
    __tablename__ = "trace_events"

    run_id: Mapped[str] = mapped_column(ForeignKey("runs.run_id"), primary_key=True)
    sequence: Mapped[int] = mapped_column(primary_key=True)
    payload: Mapped[str] = mapped_column(Text)


def enable_foreign_keys(connection: sqlite3.Connection, _record: ConnectionPoolEntry) -> None:
    connection.execute("PRAGMA foreign_keys = ON").close()


class Store:
    def __init__(self, database_path: str) -> None:
        self.engine = create_engine(
            URL.create("sqlite+pysqlite", database=database_path),
            connect_args={"check_same_thread": False, "timeout": 5},
            poolclass=StaticPool if database_path == ":memory:" else None,
        )
        listen(self.engine, "connect", enable_foreign_keys)

    def initialize(self) -> None:
        Base.metadata.create_all(self.engine)
        with Session(self.engine) as session, session.begin():
            for row in session.scalars(select(RunRow).where(RunRow.status == "running")):
                record = RunRecord.model_validate_json(row.payload)
                interrupted = record.model_copy(
                    update={
                        "status": RunStatus.FAILED,
                        "error_code": "interrupted",
                        "finished_at": datetime.now(UTC),
                    }
                )
                row.status = interrupted.status.value
                row.payload = interrupted.model_dump_json()
                previous = (
                    session.scalar(
                        select(TraceRow.sequence)
                        .where(TraceRow.run_id == row.run_id)
                        .order_by(TraceRow.sequence.desc())
                        .limit(1)
                    )
                    or 0
                )
                terminal = TraceEvent(
                    run_id=row.run_id,
                    sequence=previous + 1,
                    timestamp=datetime.now(UTC),
                    stage="run",
                    event="run_failed",
                    error_code="interrupted",
                )
                session.add(
                    TraceRow(
                        run_id=row.run_id,
                        sequence=terminal.sequence,
                        payload=terminal.model_dump_json(),
                    )
                )

    def close(self) -> None:
        self.engine.dispose()

    def ready(self) -> bool:
        try:
            with Session(self.engine) as session:
                session.execute(select(IncidentRow.incident_id).limit(1))
                session.execute(select(RunRow.run_id).limit(1))
                session.execute(select(TraceRow.run_id).limit(1))
            return True
        except SQLAlchemyError:
            return False

    def create_incident(self, incident: IncidentCreate) -> IncidentRecord:
        record = IncidentRecord(
            **incident.model_dump(),
            incident_id=f"inc_{uuid4().hex}",
            created_at=datetime.now(UTC),
        )
        with Session(self.engine) as session, session.begin():
            session.add(
                IncidentRow(incident_id=record.incident_id, payload=record.model_dump_json())
            )
        return record

    def get_incident(self, incident_id: str) -> IncidentRecord:
        with Session(self.engine) as session:
            row = session.get(IncidentRow, incident_id)
            if row is None:
                raise WorkerError(ErrorCode.NOT_FOUND)
            return IncidentRecord.model_validate_json(row.payload)

    def create_run(self, incident_id: str, max_tool_calls: int) -> RunRecord:
        self.get_incident(incident_id)
        record = RunRecord(
            run_id=f"run_{uuid4().hex}",
            incident_id=incident_id,
            status=RunStatus.RUNNING,
            created_at=datetime.now(UTC),
            max_tool_calls=max_tool_calls,
        )
        with Session(self.engine) as session, session.begin():
            session.add(
                RunRow(
                    run_id=record.run_id,
                    incident_id=incident_id,
                    status=record.status.value,
                    payload=record.model_dump_json(),
                )
            )
        return record

    def get_run(self, run_id: str) -> RunRecord:
        with Session(self.engine) as session:
            row = session.get(RunRow, run_id)
            if row is None:
                raise WorkerError(ErrorCode.NOT_FOUND)
            return RunRecord.model_validate_json(row.payload)

    def append_trace(self, event: TraceEvent) -> None:
        with Session(self.engine) as session, session.begin():
            session.add(
                TraceRow(
                    run_id=event.run_id, sequence=event.sequence, payload=event.model_dump_json()
                )
            )

    def finish_run(
        self, record: RunRecord, report: IncidentReport | None, terminal: TraceEvent
    ) -> None:
        with Session(self.engine) as session, session.begin():
            row = session.get(RunRow, record.run_id)
            if row is None:
                raise WorkerError(ErrorCode.NOT_FOUND)
            if row.status != "running":
                raise WorkerError(ErrorCode.INVALID_STATE)
            row.status = record.status.value
            row.payload = record.model_dump_json()
            row.report = report.model_dump_json() if report is not None else None
            session.add(
                TraceRow(
                    run_id=terminal.run_id,
                    sequence=terminal.sequence,
                    payload=terminal.model_dump_json(),
                )
            )

    def get_report(self, run_id: str) -> IncidentReport:
        with Session(self.engine) as session:
            row = session.get(RunRow, run_id)
            if row is None:
                raise WorkerError(ErrorCode.NOT_FOUND)
            if row.report is None:
                raise WorkerError(ErrorCode.INVALID_STATE)
            return IncidentReport.model_validate_json(row.report)

    def get_trace(self, run_id: str, offset: int = 0, limit: int = 100) -> list[TraceEvent]:
        self.get_run(run_id)
        with Session(self.engine) as session:
            rows = session.scalars(
                select(TraceRow)
                .where(TraceRow.run_id == run_id)
                .order_by(TraceRow.sequence)
                .offset(offset)
                .limit(limit)
            )
            return [TraceEvent.model_validate_json(row.payload) for row in rows]
