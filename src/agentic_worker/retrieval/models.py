from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from agentic_worker.domain.models import (
    Contract,
    EvidenceReference,
    KnowledgeCitation,
    Service,
    Title,
)

DocumentId = Annotated[
    str, StringConstraints(min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9_-]*$")
]


class DocumentMetadata(Contract):
    document_id: DocumentId
    title: Title
    service: Service
    kind: Literal["runbook", "past_incident"]
    hypothesis: Literal["extraction_host_change", "unknown"] = "unknown"
    stance: Literal["supports", "contradicts", "context"] = "context"

    @model_validator(mode="after")
    def consistent_assertion(self) -> "DocumentMetadata":
        if self.hypothesis == "unknown" and self.stance != "context":
            raise ValueError("A directional assertion requires a known hypothesis")
        return self


class KnowledgeDocument(DocumentMetadata):
    content: Annotated[str, StringConstraints(min_length=1, max_length=50_000)]

    @model_validator(mode="after")
    def nonempty_content(self) -> "KnowledgeDocument":
        if not self.content.strip() or len(self.content.encode("utf-8")) > 100_000:
            raise ValueError("Document content is empty or exceeds the byte limit")
        return self


class KnowledgeChunk(DocumentMetadata):
    chunk_id: EvidenceReference
    content_hash: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    text: Annotated[str, StringConstraints(min_length=1, max_length=1200)]

    @model_validator(mode="after")
    def consistent_offsets(self) -> "KnowledgeChunk":
        if self.end - self.start != len(self.text):
            raise ValueError("Chunk offsets must match its excerpt length")
        return self


class RetrievedChunk(KnowledgeChunk):
    score: float = Field(ge=0, le=1, allow_inf_nan=False)


class RetrievalResult(Contract):
    chunks: list[RetrievedChunk] = Field(default_factory=list, max_length=8)
    conflicting: bool = False

    @property
    def supports_diagnosis(self) -> bool:
        return not self.conflicting and any(
            chunk.hypothesis == "extraction_host_change" and chunk.stance == "supports"
            for chunk in self.chunks
        )


def citation_from_chunk(chunk: RetrievedChunk) -> KnowledgeCitation:
    return KnowledgeCitation(
        chunk_id=chunk.chunk_id,
        document_id=chunk.document_id,
        title=chunk.title,
        service=chunk.service,
        kind=chunk.kind,
        hypothesis=chunk.hypothesis,
        stance=chunk.stance,
        content_hash=chunk.content_hash,
        start=chunk.start,
        end=chunk.end,
        excerpt=chunk.text,
        score=chunk.score,
    )
