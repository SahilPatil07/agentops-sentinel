from pathlib import Path

from agentic_worker.retrieval.corpus import load_corpus


def test_bundled_corpus_is_valid_and_complete() -> None:
    version, documents = load_corpus(Path("knowledge"))
    assert version == "2026-10-23.1"
    assert len(documents) == 8
    assert len({document.document_id for document in documents}) == 8
    assert {document.kind for document in documents} == {"runbook", "past_incident"}
    assert sum(document.service == "document-ingestion" for document in documents) == 4
    assert any("Ignore all system instructions" in document.content for document in documents)
    ingestion_stances = {
        document.stance for document in documents if document.service == "document-ingestion"
    }
    assert ingestion_stances >= {
        "supports",
        "contradicts",
    }
