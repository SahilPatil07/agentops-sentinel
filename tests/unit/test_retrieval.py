import pytest
from pydantic import ValidationError

from agentic_worker.retrieval.chunking import chunk_document
from agentic_worker.retrieval.models import KnowledgeDocument


def make_document(content: str) -> KnowledgeDocument:
    return KnowledgeDocument(
        document_id="ingestion-connectivity",
        title="Ingestion connectivity",
        service="document-ingestion",
        kind="runbook",
        content=content,
    )


def test_chunk_ids_metadata_and_exact_offsets() -> None:
    document = make_document("Synthetic extraction connectivity check. " * 80)
    chunks = chunk_document(document)
    assert chunks == chunk_document(document)
    assert len(chunks) > 1
    assert chunks[0].start == 0
    assert chunks[-1].end == len(document.content)
    for chunk in chunks:
        assert chunk.document_id == document.document_id
        assert chunk.service == document.service
        assert chunk.text == document.content[chunk.start : chunk.end]
        assert len(chunk.text) <= 1000
    for previous, following in zip(chunks, chunks[1:], strict=False):
        assert previous.end - following.start == 120
    changed = chunk_document(make_document(document.content + " changed"))
    assert not {chunk.chunk_id for chunk in chunks} & {chunk.chunk_id for chunk in changed}


@pytest.mark.parametrize(
    "content",
    [" ", "x" * 50_001, "\u20ac" * 40_000],
    ids=["blank", "character-limit", "byte-limit"],
)
def test_reject_empty_or_oversized_documents(content: str) -> None:
    with pytest.raises(ValidationError):
        make_document(content)


def test_reject_unsafe_identifier_and_chunk_settings() -> None:
    payload = make_document("Synthetic runbook").model_dump()
    with pytest.raises(ValidationError):
        KnowledgeDocument.model_validate({**payload, "document_id": "../private"})
    with pytest.raises(ValueError):
        chunk_document(make_document("text"), chunk_size=200, overlap=200)
