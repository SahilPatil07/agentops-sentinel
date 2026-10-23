import asyncio
from datetime import UTC, datetime
from time import perf_counter
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langsmith import tracing_context
from pydantic import ValidationError

from agentic_worker.config import Settings
from agentic_worker.domain.models import (
    DiagnosticQuery,
    FailureCode,
    IncidentRecord,
    IncidentReport,
    KnowledgeCitation,
    Observation,
    RunRecord,
    RunRequest,
    RunStatus,
    ToolName,
    TraceEvent,
    TraceEventName,
    TraceStage,
)
from agentic_worker.llm.base import ReportProvider
from agentic_worker.persistence.store import Store
from agentic_worker.retrieval.index import KnowledgeIndex
from agentic_worker.retrieval.models import RetrievalResult, citation_from_chunk
from agentic_worker.tools.diagnostics import TOOL_NAMES, DiagnosticTools, ObservationBatch


class InvestigationState(TypedDict):
    incident: IncidentRecord
    observations: list[Observation]
    retrieval: RetrievalResult
    report: IncidentReport | None


class StateUpdate(TypedDict, total=False):
    observations: list[Observation]
    retrieval: RetrievalResult
    report: IncidentReport


class RunFailure(Exception):
    def __init__(self, code: FailureCode, status: RunStatus = RunStatus.FAILED) -> None:
        self.code = code
        self.status = status
        super().__init__(code)


def validate_report(
    report: IncidentReport,
    observations: list[Observation],
    retrieval: RetrievalResult,
    index: KnowledgeIndex,
) -> None:
    available = {item.source_id: item for item in observations}
    cited = {item.source_id: item for item in report.source_citations}
    if len(available) != len(observations) or len(cited) != len(report.source_citations):
        raise RunFailure("invalid_report")
    if cited != available:
        raise RunFailure("invalid_report")
    for fact in report.observed_facts:
        if len(fact.evidence_refs) != 1 or fact.evidence_refs[0] not in cited:
            raise RunFailure("invalid_report")
        if fact.text != cited[fact.evidence_refs[0]].summary:
            raise RunFailure("invalid_report")
    expected_knowledge = {chunk.chunk_id: citation_from_chunk(chunk) for chunk in retrieval.chunks}
    actual_knowledge = {item.chunk_id: item for item in report.knowledge_citations}
    if len(actual_knowledge) != len(report.knowledge_citations):
        raise RunFailure("invalid_report")
    if actual_knowledge != expected_knowledge:
        raise RunFailure("invalid_report")
    for chunk_id, citation in actual_knowledge.items():
        stored = index.get_chunk(chunk_id)
        if (
            stored is None
            or stored.content_hash != citation.content_hash
            or stored.start != citation.start
            or stored.end != citation.end
            or stored.text != citation.excerpt
        ):
            raise RunFailure("invalid_report")
    all_references = set(cited) | set(actual_knowledge)
    for hypothesis in report.hypotheses:
        if not set(hypothesis.evidence_refs).issubset(all_references):
            raise RunFailure("invalid_report")
        if not set(hypothesis.evidence_refs) & set(actual_knowledge):
            raise RunFailure("invalid_report")
    if report.status == "succeeded" and (not report.hypotheses or not report.observed_facts):
        raise RunFailure("invalid_report")
    if report.status == "needs_input" and (
        not report.missing_information or report.recommended_actions or report.hypotheses
    ):
        raise RunFailure("invalid_report")
    if retrieval.conflicting and report.status != "needs_input":
        raise RunFailure("invalid_report")


class InvestigationService:
    def __init__(
        self,
        store: Store,
        settings: Settings,
        provider: ReportProvider,
        tools: DiagnosticTools,
        knowledge: KnowledgeIndex,
    ) -> None:
        self.store = store
        self.settings = settings
        self.provider = provider
        self.tools = tools
        self.knowledge = knowledge

    async def investigate(self, incident_id: str, request: RunRequest) -> RunRecord:
        incident = await asyncio.to_thread(self.store.get_incident, incident_id)
        run = await asyncio.to_thread(
            self.store.create_run,
            incident_id,
            min(request.max_tool_calls, self.settings.max_tool_calls),
        )
        execution = RunExecution(self, run)
        return await execution.execute(incident)


class RunExecution:
    def __init__(self, service: InvestigationService, run: RunRecord) -> None:
        self.service = service
        self.run = run
        self.sequence = 0
        self.steps = 0
        self.tool_calls = 0

    async def emit(
        self,
        stage: TraceStage,
        event: TraceEventName,
        *,
        tool_name: ToolName | None = None,
        observations: list[Observation] | None = None,
        knowledge_citations: list[KnowledgeCitation] | None = None,
        error_code: FailureCode | None = None,
        duration_ms: float = 0.0,
    ) -> None:
        self.sequence += 1
        trace = TraceEvent(
            run_id=self.run.run_id,
            sequence=self.sequence,
            timestamp=datetime.now(UTC),
            stage=stage,
            event=event,
            tool_name=tool_name,
            observations=observations or [],
            knowledge_citations=knowledge_citations or [],
            error_code=error_code,
            duration_ms=duration_ms,
        )
        await asyncio.to_thread(self.service.store.append_trace, trace)

    async def step(self, stage: TraceStage) -> None:
        if self.steps >= self.service.settings.max_graph_steps:
            raise RunFailure("step_budget_exhausted", RunStatus.BLOCKED)
        self.steps += 1
        await self.emit(stage, "state_transition")

    async def intake(self, state: InvestigationState) -> StateUpdate:
        await self.step("intake")
        IncidentRecord.model_validate(state["incident"])
        return {}

    async def diagnose(self, state: InvestigationState) -> StateUpdate:
        await self.step("diagnostics")
        observations: list[Observation] = []
        for name in TOOL_NAMES:
            if self.tool_calls >= self.run.max_tool_calls:
                raise RunFailure("tool_budget_exhausted", RunStatus.BLOCKED)
            self.tool_calls += 1
            await self.emit("diagnostics", "tool_started", tool_name=name)
            started = perf_counter()
            try:
                output = await asyncio.wait_for(
                    self.service.tools.query(
                        name, DiagnosticQuery(service=state["incident"].service)
                    ),
                    timeout=self.service.settings.tool_timeout_seconds,
                )
                batch = ObservationBatch.model_validate(output)
                output = batch.root
                if (
                    len(batch.model_dump_json().encode("utf-8"))
                    > self.service.settings.max_tool_output_bytes
                ):
                    raise RunFailure("output_limit_exceeded", RunStatus.DEGRADED)
                if any(
                    item.tool_name != name or item.service != state["incident"].service
                    for item in output
                ):
                    raise RunFailure("tool_failed", RunStatus.DEGRADED)
            except TimeoutError as exc:
                await self.emit(
                    "diagnostics", "tool_failed", tool_name=name, error_code="tool_timeout"
                )
                raise RunFailure("tool_timeout", RunStatus.DEGRADED) from exc
            except RunFailure as exc:
                await self.emit("diagnostics", "tool_failed", tool_name=name, error_code=exc.code)
                raise
            except Exception as exc:
                await self.emit(
                    "diagnostics", "tool_failed", tool_name=name, error_code="tool_failed"
                )
                raise RunFailure("tool_failed", RunStatus.DEGRADED) from exc
            observations.extend(output)
            await self.emit(
                "diagnostics",
                "tool_completed",
                tool_name=name,
                observations=output,
                duration_ms=(perf_counter() - started) * 1000,
            )
        return {"observations": ObservationBatch.model_validate(observations).root}

    async def retrieve(self, state: InvestigationState) -> StateUpdate:
        await self.step("retrieval")
        await self.emit("retrieval", "retrieval_started")
        incident = state["incident"]
        query = f"{incident.title} {incident.description} {incident.service}"
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    self.service.knowledge.search,
                    query,
                    incident.service,
                    self.service.settings.retrieval_top_k,
                    self.service.settings.retrieval_min_score,
                ),
                timeout=self.service.settings.retrieval_timeout_seconds,
            )
        except TimeoutError as exc:
            await self.emit("retrieval", "retrieval_failed", error_code="retrieval_timeout")
            raise RunFailure("retrieval_timeout", RunStatus.DEGRADED) from exc
        except Exception as exc:
            await self.emit("retrieval", "retrieval_failed", error_code="retrieval_failed")
            raise RunFailure("retrieval_failed", RunStatus.DEGRADED) from exc
        citations = [citation_from_chunk(chunk) for chunk in result.chunks]
        await self.emit("retrieval", "retrieval_completed", knowledge_citations=citations)
        return {"retrieval": result}

    async def report(self, state: InvestigationState) -> StateUpdate:
        await self.step("report")
        for attempt in range(self.service.settings.max_provider_attempts):
            await self.emit("report", "provider_started")
            started = perf_counter()
            try:
                raw = await asyncio.wait_for(
                    self.service.provider.generate_report(
                        state["incident"], state["observations"], state["retrieval"]
                    ),
                    timeout=self.service.settings.provider_timeout_seconds,
                )
                if len(raw.encode("utf-8")) > self.service.settings.max_report_bytes:
                    raise RunFailure("output_limit_exceeded")
                report = IncidentReport.model_validate_json(raw)
            except (TimeoutError, ValidationError) as exc:
                code: FailureCode = (
                    "provider_timeout" if isinstance(exc, TimeoutError) else "invalid_report"
                )
                await self.emit("report", "provider_failed", error_code=code)
                if attempt + 1 == self.service.settings.max_provider_attempts:
                    raise RunFailure(code) from exc
            except RunFailure as exc:
                await self.emit("report", "provider_failed", error_code=exc.code)
                raise
            except Exception as exc:
                await self.emit("report", "provider_failed", error_code="provider_failed")
                raise RunFailure("provider_failed") from exc
            else:
                await self.emit(
                    "report", "provider_completed", duration_ms=(perf_counter() - started) * 1000
                )
                return {"report": report}
        raise RunFailure("provider_failed")

    async def validate(self, state: InvestigationState) -> StateUpdate:
        await self.step("validate")
        report = state["report"]
        if report is None:
            raise RunFailure("invalid_report")
        validate_report(report, state["observations"], state["retrieval"], self.service.knowledge)
        return {}

    async def execute(self, incident: IncidentRecord) -> RunRecord:
        started = perf_counter()
        report: IncidentReport | None = None
        error_code: FailureCode | None = None
        cancelled = False
        await self.emit("run", "run_started")
        try:
            graph = StateGraph(InvestigationState)
            graph.add_node("intake", self.intake)
            graph.add_node("diagnostics", self.diagnose)
            graph.add_node("retrieval", self.retrieve)
            graph.add_node("report", self.report)
            graph.add_node("validate", self.validate)
            graph.add_edge(START, "intake")
            graph.add_edge("intake", "retrieval")
            graph.add_edge("retrieval", "diagnostics")
            graph.add_edge("diagnostics", "report")
            graph.add_edge("report", "validate")
            graph.add_edge("validate", END)
            initial: InvestigationState = {
                "incident": incident,
                "observations": [],
                "retrieval": RetrievalResult(),
                "report": None,
            }
            with tracing_context(enabled=False):
                async with asyncio.timeout(self.service.settings.workflow_timeout_seconds):
                    result = await graph.compile().ainvoke(
                        initial,
                        config={"recursion_limit": self.service.settings.max_graph_steps + 2},
                    )
            report = IncidentReport.model_validate(result["report"])
            status = RunStatus(report.status)
        except RunFailure as exc:
            status, error_code = exc.status, exc.code
        except TimeoutError:
            status, error_code = RunStatus.FAILED, "workflow_timeout"
        except asyncio.CancelledError:
            status, error_code = RunStatus.FAILED, "interrupted"
            cancelled = True
        except Exception:
            status, error_code = RunStatus.FAILED, "workflow_failed"
        completed = self.run.model_copy(
            update={
                "status": status,
                "error_code": error_code,
                "finished_at": datetime.now(UTC),
                "tool_calls": self.tool_calls,
                "steps": self.steps,
                "provider_name": self.service.provider.provider_name,
                "model_name": self.service.provider.model_name,
            }
        )
        terminal = TraceEvent(
            run_id=self.run.run_id,
            sequence=self.sequence + 1,
            timestamp=datetime.now(UTC),
            stage="run",
            event="run_completed" if report is not None else "run_failed",
            error_code=error_code,
            duration_ms=(perf_counter() - started) * 1000,
        )
        await asyncio.to_thread(self.service.store.finish_run, completed, report, terminal)
        if cancelled:
            raise asyncio.CancelledError
        return completed
