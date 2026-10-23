from datetime import datetime
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


class IncidentRecord(IncidentCreate):
    incident_id: str
    created_at: datetime
    status: Literal["created"] = "created"


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


ToolName = Literal["query_logs", "query_metrics", "compare_deployments", "get_recent_incidents"]
TraceStage = Literal["run", "intake", "retrieval", "diagnostics", "report", "validate"]
TraceEventName = Literal[
    "run_started",
    "state_transition",
    "retrieval_started",
    "retrieval_completed",
    "retrieval_failed",
    "tool_started",
    "tool_completed",
    "tool_failed",
    "provider_started",
    "provider_completed",
    "provider_failed",
    "run_completed",
    "run_failed",
]
FailureCode = Literal[
    "step_budget_exhausted",
    "tool_budget_exhausted",
    "tool_timeout",
    "tool_failed",
    "provider_timeout",
    "provider_failed",
    "invalid_report",
    "output_limit_exceeded",
    "workflow_timeout",
    "workflow_failed",
    "interrupted",
    "retrieval_timeout",
    "retrieval_failed",
]


class RunRequest(Contract):
    mode: Literal["investigate"] = "investigate"
    max_tool_calls: int = Field(default=8, ge=1, le=16)


class DiagnosticQuery(Contract):
    service: Service


class Observation(Contract):
    source_id: EvidenceReference
    tool_name: ToolName
    service: Service
    summary: Description
    signal: Literal[
        "dependency_unreachable",
        "error_rate",
        "dependency_host_changed",
        "prior_dependency_incident",
    ]
    value: Annotated[str, StringConstraints(max_length=500)] | float
    source_type: Literal["synthetic_diagnostic"] = "synthetic_diagnostic"


class KnowledgeCitation(Contract):
    chunk_id: EvidenceReference
    document_id: EvidenceReference
    title: Title
    service: Service
    kind: Literal["runbook", "past_incident"]
    hypothesis: Literal["extraction_host_change", "unknown"]
    stance: Literal["supports", "contradicts", "context"]
    content_hash: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    excerpt: Annotated[str, StringConstraints(min_length=1, max_length=1200)]
    score: float = Field(ge=0, le=1, allow_inf_nan=False)


class ObservedFact(Contract):
    text: Description
    evidence_refs: list[EvidenceReference] = Field(min_length=1, max_length=20)


class Hypothesis(Contract):
    description: Description
    evidence_refs: list[EvidenceReference] = Field(min_length=1, max_length=20)
    confidence: Literal["low", "medium"]
    confidence_rationale: Description


class RecommendedAction(Contract):
    action_id: EvidenceReference
    title: Title
    risk: Literal["low", "medium", "high"]
    preconditions: list[EvidenceReference] = Field(min_length=1, max_length=10)
    expected_result: Description
    verification: list[EvidenceReference] = Field(min_length=1, max_length=10)
    rollback: Description
    approval_required: Literal[True] = True
    simulated: Literal[True] = True
    execution_status: Literal["not_executed"] = "not_executed"


class IncidentReport(Contract):
    summary: Description
    status: Literal["succeeded", "needs_input"]
    observed_facts: list[ObservedFact] = Field(max_length=20)
    hypotheses: list[Hypothesis] = Field(max_length=5)
    missing_information: list[EvidenceReference] = Field(max_length=10)
    recommended_actions: list[RecommendedAction] = Field(max_length=5)
    source_citations: list[Observation] = Field(max_length=20)
    knowledge_citations: list[KnowledgeCitation] = Field(default_factory=list, max_length=8)
    limitations: list[EvidenceReference] = Field(min_length=1, max_length=10)


class RunRecord(Contract):
    run_id: str
    incident_id: str
    status: RunStatus
    created_at: datetime
    finished_at: datetime | None = None
    max_tool_calls: int
    tool_calls: int = 0
    steps: int = 0
    provider_name: str = "deterministic_mock"
    model_name: str = "rules-v1"
    error_code: FailureCode | None = None


class TraceEvent(Contract):
    run_id: str
    sequence: int = Field(ge=1)
    timestamp: datetime
    stage: TraceStage
    event: TraceEventName
    duration_ms: float = Field(default=0.0, ge=0, allow_inf_nan=False)
    tool_name: ToolName | None = None
    observations: list[Observation] = Field(default_factory=list, max_length=20)
    knowledge_citations: list[KnowledgeCitation] = Field(default_factory=list, max_length=8)
    error_code: FailureCode | None = None
