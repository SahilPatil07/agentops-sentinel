import sqlite3
from pathlib import Path

import pytest

from agentic_worker.retrieval.index import KnowledgeIndex
from agentic_worker.retrieval.models import KnowledgeDocument


def document(content: str, *, stance: str = "supports") -> KnowledgeDocument:
    return KnowledgeDocument.model_validate(
        {
            "document_id": "ingestion-connectivity",
            "title": "Ingestion connectivity",
            "service": "document-ingestion",
            "kind": "runbook",
            "hypothesis": "extraction_host_change",
            "stance": stance,
            "content": content,
        }
    )


def test_index_persists_retrieves_and_resolves_chunks(tmp_path: Path) -> None:
    path = str(tmp_path / "knowledge-index")
    index = KnowledgeIndex(path)
    original = document("Extraction host connection errors after deployment. " * 30)
    assert index.ingest([original]) == 2
    first = index.search("extraction host connection deployment", "document-ingestion", 4, 0.1)
    assert first.chunks
    assert first.supports_diagnosis
    resolved = index.get_chunk(first.chunks[0].chunk_id)
    assert resolved is not None
    assert resolved.text == original.content[resolved.start : resolved.end]

    restarted = KnowledgeIndex(path)
    assert restarted.search("extraction host", "document-ingestion", 4, 0.1).chunks
    assert [item.document_id for item in restarted.list_documents()] == ["ingestion-connectivity"]


def test_reingestion_replaces_stale_chunks_and_service_filter(tmp_path: Path) -> None:
    index = KnowledgeIndex(str(tmp_path / "knowledge-index"))
    original = document("Extraction host old evidence. " * 80)
    index.ingest([original])
    results = index.search("old evidence", "document-ingestion", 8, 0)
    old_ids = {chunk.chunk_id for chunk in results.chunks}
    updated = document("Extraction host replacement evidence.")
    index.ingest([updated])
    new_ids = {
        chunk.chunk_id
        for chunk in index.search("replacement evidence", "document-ingestion", 8, 0).chunks
    }
    assert old_ids.isdisjoint(new_ids)
    assert all(index.get_chunk(chunk_id) is None for chunk_id in old_ids)
    assert index.search("replacement", "other-service", 4, 0).chunks == []


def test_index_rejects_malformed_stored_embedding(tmp_path: Path) -> None:
    index = KnowledgeIndex(str(tmp_path / "knowledge-index"))
    index.ingest([document("Extraction host evidence.")])
    with sqlite3.connect(index.database_path) as connection:
        connection.execute("UPDATE knowledge_chunks SET embedding = '[1.0]'")
    with pytest.raises(ValueError, match="dimensions"):
        index.search("extraction", "document-ingestion", 2, 0)
