from importlib.resources import files

from pydantic import Field, RootModel

from agentic_worker.domain.models import DiagnosticQuery, Observation, ToolDefinition, ToolName

TOOL_REGISTRY: dict[ToolName, ToolDefinition] = {
    "query_logs": ToolDefinition(
        name="query_logs", description="Query bounded synthetic service logs."
    ),
    "query_metrics": ToolDefinition(
        name="query_metrics", description="Query bounded synthetic service metrics."
    ),
    "compare_deployments": ToolDefinition(
        name="compare_deployments", description="Compare synthetic deployment snapshots."
    ),
    "get_recent_incidents": ToolDefinition(
        name="get_recent_incidents", description="Read related synthetic incident history."
    ),
}
TOOL_NAMES: tuple[ToolName, ...] = tuple(TOOL_REGISTRY)


class ObservationBatch(RootModel[list[Observation]]):
    root: list[Observation] = Field(max_length=20)


class DiagnosticTools:
    def __init__(self) -> None:
        source = (
            files("agentic_worker.tools").joinpath("seed_data.json").read_text(encoding="utf-8")
        )
        self._snapshot = ObservationBatch.model_validate_json(source).root
        if len({item.source_id for item in self._snapshot}) != len(self._snapshot):
            raise ValueError("Duplicate synthetic diagnostic source IDs")

    async def query(self, name: ToolName, query: DiagnosticQuery) -> list[Observation]:
        if name not in TOOL_REGISTRY:
            raise ValueError("Unsupported diagnostic tool")
        return [
            item
            for item in self._snapshot
            if item.tool_name == name and item.service == query.service
        ]
