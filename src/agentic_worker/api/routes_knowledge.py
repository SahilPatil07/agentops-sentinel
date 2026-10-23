from fastapi import APIRouter

from agentic_worker.domain.errors import ErrorCode, WorkerError
from agentic_worker.retrieval.index import KnowledgeIndex
from agentic_worker.retrieval.models import DocumentMetadata, KnowledgeChunk


def knowledge_routes(index: KnowledgeIndex) -> APIRouter:
    router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])

    @router.get("/documents", response_model=list[DocumentMetadata])
    def list_documents() -> list[DocumentMetadata]:
        return index.list_documents()

    @router.get("/chunks/{chunk_id}", response_model=KnowledgeChunk)
    def get_chunk(chunk_id: str) -> KnowledgeChunk:
        chunk = index.get_chunk(chunk_id)
        if chunk is None:
            raise WorkerError(ErrorCode.NOT_FOUND)
        return chunk

    return router
