from typing import Literal

from agentic_worker.domain.errors import ErrorCode, WorkerError
from agentic_worker.domain.models import (
    ActionExecutionRecord,
    ActionExecutionRequest,
    ApprovalRecord,
    ApprovalRequest,
    RecommendedAction,
)
from agentic_worker.persistence.store import Store


class ActionService:
    def __init__(self, store: Store) -> None:
        self.store = store

    def decide(
        self,
        run_id: str,
        action_id: str,
        request: ApprovalRequest,
        decision: Literal["approved", "rejected"],
    ) -> ApprovalRecord:
        action = self._current_action(run_id, action_id)
        if request.plan_version != action.plan_version:
            raise WorkerError(ErrorCode.INVALID_STATE)
        if self.store.get_action_execution(run_id, action_id, action.plan_version) is not None:
            raise WorkerError(ErrorCode.INVALID_STATE)
        return self.store.record_approval(run_id, action_id, request, decision)

    def execute(
        self, run_id: str, action_id: str, request: ActionExecutionRequest
    ) -> ActionExecutionRecord:
        action = self._current_action(run_id, action_id)
        if request.plan_version != action.plan_version:
            raise WorkerError(ErrorCode.INVALID_STATE)
        existing = self.store.get_action_execution(run_id, action_id, action.plan_version)
        if existing is not None:
            return existing
        approval = self.store.get_latest_approval(run_id, action_id, action.plan_version)
        if approval is None or approval.decision != "approved":
            raise WorkerError(ErrorCode.POLICY_BLOCKED)
        return self.store.record_action_execution(
            run_id, action_id, action.plan_version, approval.approval_id
        )

    def _current_action(self, run_id: str, action_id: str) -> RecommendedAction:
        report = self.store.get_report(run_id)
        action = next(
            (item for item in report.recommended_actions if item.action_id == action_id), None
        )
        if action is None:
            raise WorkerError(ErrorCode.NOT_FOUND)
        return action
