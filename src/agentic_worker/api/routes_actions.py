from fastapi import APIRouter

from agentic_worker.actions.service import ActionService
from agentic_worker.domain.models import (
    ActionExecutionRecord,
    ActionExecutionRequest,
    ApprovalRecord,
    ApprovalRequest,
)


def action_routes(service: ActionService) -> APIRouter:
    router = APIRouter(prefix="/api/v1/runs/{run_id}/actions/{action_id}", tags=["actions"])

    @router.post("/approve", response_model=ApprovalRecord)
    def approve(run_id: str, action_id: str, request: ApprovalRequest) -> ApprovalRecord:
        return service.decide(run_id, action_id, request, "approved")

    @router.post("/reject", response_model=ApprovalRecord)
    def reject(run_id: str, action_id: str, request: ApprovalRequest) -> ApprovalRecord:
        return service.decide(run_id, action_id, request, "rejected")

    @router.post("/execute", response_model=ActionExecutionRecord)
    def execute(
        run_id: str, action_id: str, request: ActionExecutionRequest
    ) -> ActionExecutionRecord:
        return service.execute(run_id, action_id, request)

    return router
