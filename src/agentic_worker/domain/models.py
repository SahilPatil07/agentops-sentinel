from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Title = Annotated[
    str, StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=200)
]
Description = Annotated[
    str, StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=10_000)
]
Service = Annotated[
    str,
    StringConstraints(
        strict=True,
        strip_whitespace=True,
        min_length=1,
        max_length=100,
        pattern=r"^[a-z0-9][a-z0-9_-]*$",
    ),
]
EvidenceReference = Annotated[
    str, StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=500)
]


class RunStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    NEEDS_INPUT = "needs_input"
    BLOCKED = "blocked"
    FAILED = "failed"
    DEGRADED = "degraded"


class IncidentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    title: Title
    description: Description
    service: Service
    severity: Literal["low", "medium", "high", "critical"]
    environment: Literal["demo"] = "demo"
    evidence: list[EvidenceReference] = Field(default_factory=list, max_length=20)
