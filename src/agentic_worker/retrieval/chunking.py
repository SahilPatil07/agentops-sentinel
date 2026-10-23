from hashlib import sha256

from agentic_worker.retrieval.models import KnowledgeChunk, KnowledgeDocument


def chunk_document(
    document: KnowledgeDocument, chunk_size: int = 1000, overlap: int = 120
) -> list[KnowledgeChunk]:
    if not 200 <= chunk_size <= 1200 or not 0 <= overlap < chunk_size:
        raise ValueError("Invalid chunk size or overlap")
    digest = sha256(document.content.encode("utf-8")).hexdigest()
    metadata = document.model_dump(exclude={"content"})
    chunks: list[KnowledgeChunk] = []
    start = 0
    while start < len(document.content):
        end = min(start + chunk_size, len(document.content))
        chunks.append(
            KnowledgeChunk(
                **metadata,
                chunk_id=f"{document.document_id}:{digest[:16]}:{start}:{end}",
                content_hash=digest,
                start=start,
                end=end,
                text=document.content[start:end],
            )
        )
        if len(chunks) > 100:
            raise ValueError("Document produces too many chunks")
        if end == len(document.content):
            break
        start = end - overlap
    return chunks
