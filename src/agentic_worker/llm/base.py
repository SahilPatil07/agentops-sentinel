from typing import Protocol

from agentic_worker.domain.models import IncidentRecord, Observation
from agentic_worker.retrieval.models import RetrievalResult


class ReportProvider(Protocol):
    provider_name: str
    model_name: str

    async def generate_report(
        self,
        incident: IncidentRecord,
        observations: list[Observation],
        retrieval: RetrievalResult,
    ) -> str: ...
