import sqlite3
from datetime import UTC, datetime
from typing import Literal
from uuid import NAMESPACE_URL, uuid4, uuid5

from sqlalchemy import URL, ForeignKey, String, Text, create_engine, select
from sqlalchemy.event import listen
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from sqlalchemy.pool import ConnectionPoolEntry, StaticPool

from agentic_worker.domain.errors import ErrorCode, WorkerError
from agentic_worker.domain.models import (
    ActionExecutionRecord,
    ApprovalRecord,
    ApprovalRequest,
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


class ApprovalRow(Base):
    __tablename__ = "approval_decisions"

    approval_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.run_id"), index=True)
    action_id: Mapped[str] = mapped_column(String(500), index=True)
    plan_version: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(index=True)
    payload: Mapped[str] = mapped_column(Text)


class ActionExecutionRow(Base):
    __tablename__ = "action_executions"

    execution_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.run_id"), index=True)
    action_id: Mapped[str] = mapped_column(String(500), index=True)
    plan_version: Mapped[str] = mapped_column(String(64), index=True)
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
                session.execute(select(ApprovalRow.approval_id).limit(1))
                session.execute(select(ActionExecutionRow.execution_id).limit(1))
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

    def record_approval(
        self,
        run_id: str,
        action_id: str,
        request: ApprovalRequest,
        decision: Literal["approved", "rejected"],
    ) -> ApprovalRecord:
        record = ApprovalRecord(
            approval_id=f"approval_{uuid4().hex}",
            run_id=run_id,
            action_id=action_id,
            reviewer=request.reviewer,
            plan_version=request.plan_version,
            decision=decision,
            created_at=datetime.now(UTC),
        )
        with Session(self.engine) as session, session.begin():
            session.add(
                ApprovalRow(
                    approval_id=record.approval_id,
                    run_id=run_id,
                    action_id=action_id,
                    plan_version=request.plan_version,
                    created_at=record.created_at,
                    payload=record.model_dump_json(),
                )
            )
        return record

    def get_latest_approval(
        self, run_id: str, action_id: str, plan_version: str
    ) -> ApprovalRecord | None:
        with Session(self.engine) as session:
            row = session.scalar(
                select(ApprovalRow)
                .where(
                    ApprovalRow.run_id == run_id,
                    ApprovalRow.action_id == action_id,
                    ApprovalRow.plan_version == plan_version,
                )
                .order_by(ApprovalRow.created_at.desc(), ApprovalRow.approval_id.desc())
                .limit(1)
            )
            return ApprovalRecord.model_validate_json(row.payload) if row is not None else None

    def get_action_execution(
        self, run_id: str, action_id: str, plan_version: str
    ) -> ActionExecutionRecord | None:
        with Session(self.engine) as session:
            row = session.scalar(
                select(ActionExecutionRow).where(
                    ActionExecutionRow.run_id == run_id,
                    ActionExecutionRow.action_id == action_id,
                    ActionExecutionRow.plan_version == plan_version,
                )
            )
            return (
                ActionExecutionRecord.model_validate_json(row.payload) if row is not None else None
            )

    def record_action_execution(
        self, run_id: str, action_id: str, plan_version: str, approval_id: str
    ) -> ActionExecutionRecord:
        identity = f"{run_id}:{action_id}:{plan_version}"
        execution_id = f"execution_{uuid5(NAMESPACE_URL, identity).hex}"
        record = ActionExecutionRecord(
            execution_id=execution_id,
            approval_id=approval_id,
            run_id=run_id,
            action_id=action_id,
            plan_version=plan_version,
            result="The approved remediation was simulated; no external state was changed.",
            created_at=datetime.now(UTC),
        )
        try:
            with Session(self.engine) as session, session.begin():
                session.add(
                    ActionExecutionRow(
                        execution_id=record.execution_id,
                        run_id=run_id,
                        action_id=action_id,
                        plan_version=plan_version,
                        payload=record.model_dump_json(),
                    )
                )
        except IntegrityError:
            existing = self.get_action_execution(run_id, action_id, plan_version)
            if existing is None:
                raise
            return existing
        return record
