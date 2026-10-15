from typing import Literal

from pydantic import BaseModel, ConfigDict

from agentic_worker.domain.errors import ErrorCode


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["alive", "ready", "not_ready"]


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: ErrorCode
    message: str
    request_id: str
