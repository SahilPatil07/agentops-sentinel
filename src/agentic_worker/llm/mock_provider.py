from agentic_worker.domain.models import (
    Hypothesis,
    IncidentRecord,
    IncidentReport,
    Observation,
    ObservedFact,
    RecommendedAction,
)
from agentic_worker.retrieval.models import RetrievalResult, citation_from_chunk


class MockProvider:
    provider_name = "deterministic_mock"
    model_name = "rules-v1"

    async def generate_report(
        self,
        incident: IncidentRecord,
        observations: list[Observation],
        retrieval: RetrievalResult,
    ) -> str:
        evidence = [item for item in observations if item.service == incident.service]
        signals = {item.signal: item for item in evidence}
        unreachable = signals.get("dependency_unreachable")
        deployment = signals.get("dependency_host_changed")
        metric = signals.get("error_rate")
        supported = (
            unreachable is not None
            and deployment is not None
            and metric is not None
            and unreachable.value == deployment.value
            and isinstance(metric.value, float)
            and metric.value > 0.1
        )
        hypotheses: list[Hypothesis] = []
        actions: list[RecommendedAction] = []
        grounded = supported and retrieval.supports_diagnosis
        supporting_chunks = [
            chunk
            for chunk in retrieval.chunks
            if chunk.hypothesis == "extraction_host_change" and chunk.stance == "supports"
        ]
        if (
            grounded
            and unreachable is not None
            and deployment is not None
            and metric is not None
            and supporting_chunks
        ):
            hypotheses.append(
                Hypothesis(
                    description=(
                        "A changed extraction-host setting may explain "
                        "the synthetic ingestion outage."
                    ),
                    evidence_refs=[
                        unreachable.source_id,
                        deployment.source_id,
                        metric.source_id,
                        supporting_chunks[0].chunk_id,
                    ],
                    confidence="medium",
                    confidence_rationale=(
                        "The unreachable host matches the deployment change, "
                        "alongside elevated errors. "
                        "Correlation in a synthetic snapshot is not proof of causation."
                    ),
                )
            )
            actions.append(
                RecommendedAction(
                    action_id="review-extraction-host",
                    title="Review the extraction-host configuration",
                    risk="medium",
                    preconditions=[
                        "Confirm the intended host with the service owner.",
                        "Obtain approval tied to a reviewed simulation plan before changes.",
                    ],
                    expected_result=(
                        "A later approved simulation would restore dependency connectivity."
                    ),
                    verification=[
                        "Compare the intended host with the deployment configuration.",
                        "Check extraction connectivity and the ingestion error ratio.",
                    ],
                    rollback=(
                        "Retain the previous configuration and restore it if verification fails."
                    ),
                )
            )
        report = IncidentReport(
            summary=(
                "The synthetic snapshot supports a deployment-related connectivity hypothesis."
                if grounded
                else (
                    "Retrieved sources conflict, so the cause remains uncertain."
                    if retrieval.conflicting
                    else "There is insufficient combined evidence to identify a cause."
                )
            ),
            status="succeeded" if grounded else "needs_input",
            observed_facts=[
                ObservedFact(text=item.summary, evidence_refs=[item.source_id]) for item in evidence
            ],
            hypotheses=hypotheses,
            recommended_actions=actions,
            missing_information=[]
            if grounded
            else [
                "Resolve conflicting sources or provide relevant runbook and diagnostic evidence."
                if retrieval.conflicting
                else "Provide relevant runbook, log, metric, and deployment evidence."
            ],
            source_citations=evidence,
            knowledge_citations=[citation_from_chunk(chunk) for chunk in retrieval.chunks],
            limitations=[
                "Rules-based mock over fixed synthetic diagnostics and local documents.",
                "Hashing retrieval is a reproducible lexical baseline, not semantic understanding.",
                "All actions are recommendations only; nothing was executed.",
            ],
        )
        return report.model_dump_json()
