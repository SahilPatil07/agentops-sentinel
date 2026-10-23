import json
import sqlite3
from pathlib import Path

from agentic_worker.retrieval.chunking import chunk_document
from agentic_worker.retrieval.embedding import HashingEmbedder
from agentic_worker.retrieval.models import (
    DocumentMetadata,
    KnowledgeChunk,
    KnowledgeDocument,
    RetrievalResult,
    RetrievedChunk,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS knowledge_chunks (
    chunk_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    title TEXT NOT NULL,
    service TEXT NOT NULL,
    kind TEXT NOT NULL,
    hypothesis TEXT NOT NULL,
    stance TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    start_offset INTEGER NOT NULL,
    end_offset INTEGER NOT NULL,
    text TEXT NOT NULL,
    embedding TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_knowledge_document ON knowledge_chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_service ON knowledge_chunks(service);
"""


class KnowledgeIndex:
    def __init__(self, path: str, embedder: HashingEmbedder | None = None) -> None:
        directory = Path(path)
        directory.mkdir(parents=True, exist_ok=True)
        self.database_path = directory / "knowledge.sqlite3"
        self.embedder = embedder or HashingEmbedder()
        with self._connect() as connection:
            connection.executescript(SCHEMA)

    def ingest(self, documents: list[KnowledgeDocument]) -> int:
        if not 1 <= len(documents) <= 100:
            raise ValueError("Ingestion batch must contain between 1 and 100 documents")
        if len({document.document_id for document in documents}) != len(documents):
            raise ValueError("Duplicate document IDs in ingestion batch")
        total = 0
        with self._connect() as connection:
            for document in documents:
                chunks = chunk_document(document)
                embeddings = self.embedder.embed([chunk.text for chunk in chunks])
                connection.execute(
                    "DELETE FROM knowledge_chunks WHERE document_id = ?",
                    (document.document_id,),
                )
                connection.executemany(
                    """
                    INSERT INTO knowledge_chunks (
                        chunk_id, document_id, title, service, kind, hypothesis, stance,
                        content_hash, start_offset, end_offset, text, embedding
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            chunk.chunk_id,
                            chunk.document_id,
                            chunk.title,
                            chunk.service,
                            chunk.kind,
                            chunk.hypothesis,
                            chunk.stance,
                            chunk.content_hash,
                            chunk.start,
                            chunk.end,
                            chunk.text,
                            json.dumps(embedding, separators=(",", ":")),
                        )
                        for chunk, embedding in zip(chunks, embeddings, strict=True)
                    ],
                )
                total += len(chunks)
        return total

    def ready(self) -> bool:
        try:
            with self._connect() as connection:
                connection.execute("SELECT COUNT(*) FROM knowledge_chunks").fetchone()
            return True
        except sqlite3.Error:
            return False

    def search(self, query: str, service: str, top_k: int, min_score: float) -> RetrievalResult:
        if not query.strip() or not 1 <= top_k <= 8 or not 0 <= min_score <= 1:
            raise ValueError("Invalid retrieval query or bounds")
        query_embedding = self.embedder.embed([query])[0]
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM knowledge_chunks WHERE service = ?", (service,)
            ).fetchall()
        ranked: list[RetrievedChunk] = []
        for row in rows:
            embedding = json.loads(row["embedding"])
            if not isinstance(embedding, list) or len(embedding) != self.embedder.dimensions:
                raise ValueError("Stored embedding does not match the expected dimensions")
            score = sum(
                query_value * float(stored_value)
                for query_value, stored_value in zip(query_embedding, embedding, strict=True)
            )
            score = max(0.0, min(1.0, score))
            if score >= min_score:
                ranked.append(
                    RetrievedChunk.model_validate({**self._chunk_data(row), "score": score})
                )
        ranked.sort(key=lambda chunk: (-chunk.score, chunk.chunk_id))
        chunks = ranked[:top_k]
        stances = {
            chunk.stance
            for chunk in chunks
            if chunk.hypothesis != "unknown" and chunk.stance != "context"
        }
        return RetrievalResult(chunks=chunks, conflicting=stances == {"supports", "contradicts"})

    def list_documents(self) -> list[DocumentMetadata]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT DISTINCT document_id, title, service, kind, hypothesis, stance
                FROM knowledge_chunks ORDER BY document_id
                """
            ).fetchall()
        return [DocumentMetadata.model_validate(dict(row)) for row in rows]

    def get_chunk(self, chunk_id: str) -> KnowledgeChunk | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM knowledge_chunks WHERE chunk_id = ?", (chunk_id,)
            ).fetchone()
        return KnowledgeChunk.model_validate(self._chunk_data(row)) if row is not None else None

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=5)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _chunk_data(row: sqlite3.Row) -> dict[str, object]:
        return {
            "chunk_id": row["chunk_id"],
            "document_id": row["document_id"],
            "title": row["title"],
            "service": row["service"],
            "kind": row["kind"],
            "hypothesis": row["hypothesis"],
            "stance": row["stance"],
            "content_hash": row["content_hash"],
            "start": row["start_offset"],
            "end": row["end_offset"],
            "text": row["text"],
        }
