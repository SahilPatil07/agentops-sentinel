from typing import Annotated

from fastapi import APIRouter, Query

from agentic_worker.domain.models import IncidentReport, RunRecord, RunRequest, TraceEvent
from agentic_worker.orchestration.graph import InvestigationService


def run_routes(service: InvestigationService) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["investigations"])

    @router.post("/incidents/{incident_id}/runs", response_model=RunRecord)
    async def start_run(incident_id: str, request: RunRequest) -> RunRecord:
        return await service.investigate(incident_id, request)

    @router.get("/runs/{run_id}", response_model=RunRecord)
    def get_run(run_id: str) -> RunRecord:
        return service.store.get_run(run_id)

    @router.get("/runs/{run_id}/report", response_model=IncidentReport)
    def get_report(run_id: str) -> IncidentReport:
        return service.store.get_report(run_id)

    @router.get("/runs/{run_id}/trace", response_model=list[TraceEvent])
    def get_trace(
        run_id: str,
        offset: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(ge=1, le=100)] = 100,
    ) -> list[TraceEvent]:
        return service.store.get_trace(run_id, offset, limit)

    return router
