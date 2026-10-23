from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from agentic_worker.api.middleware import RequestBoundaryMiddleware
from agentic_worker.api.routes_incidents import incident_routes
from agentic_worker.api.routes_knowledge import knowledge_routes
from agentic_worker.api.routes_runs import run_routes
from agentic_worker.api.schemas import ErrorResponse, HealthResponse
from agentic_worker.config import Settings
from agentic_worker.domain.errors import ErrorCode, WorkerError
from agentic_worker.llm.mock_provider import MockProvider
from agentic_worker.observability.logging import configure_logging
from agentic_worker.orchestration.graph import InvestigationService
from agentic_worker.persistence.store import Store
from agentic_worker.retrieval.index import KnowledgeIndex
from agentic_worker.retrieval.ingest import sync_corpus
from agentic_worker.tools.diagnostics import DiagnosticTools


def create_app(settings: Settings | None = None) -> FastAPI:
    configuration = settings if settings is not None else Settings()
    store = Store(configuration.database_path)
    knowledge = KnowledgeIndex(configuration.vector_store_path)
    service = InvestigationService(
        store, configuration, MockProvider(), DiagnosticTools(), knowledge
    )
    ready = False

    @asynccontextmanager
    async def lifespan(_application: FastAPI) -> AsyncIterator[None]:
        nonlocal ready
        configure_logging(configuration.log_level)
        try:
            store.initialize()
            if not knowledge.list_documents():
                sync_corpus(knowledge, Path(configuration.knowledge_path))
            ready = True
            yield
        finally:
            ready = False
            store.close()

    application = FastAPI(
        title="AgentOps Sentinel",
        version="0.1.0",
        debug=False,
        lifespan=lifespan,
        responses={
            status: {"model": ErrorResponse} for status in (400, 403, 404, 409, 413, 422, 500)
        },
    )
    application.state.settings = configuration
    application.state.store = store
    application.state.investigations = service
    application.state.knowledge = knowledge
    application.add_middleware(RequestBoundaryMiddleware, settings=configuration)
    application.include_router(incident_routes(store))
    application.include_router(run_routes(service))
    application.include_router(knowledge_routes(knowledge))

    def error_response(
        request: Request, code: ErrorCode, message: str, status_code: int
    ) -> JSONResponse:
        payload = ErrorResponse(code=code, message=message, request_id=request.state.request_id)
        return JSONResponse(payload.model_dump(mode="json"), status_code=status_code)

    @application.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, _exc: RequestValidationError) -> JSONResponse:
        return error_response(
            request, ErrorCode.INVALID_REQUEST, "Request does not match the required schema.", 422
        )

    @application.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
        code = ErrorCode.NOT_FOUND if exc.status_code == 404 else ErrorCode.HTTP_ERROR
        response = error_response(request, code, "HTTP request failed.", exc.status_code)
        if exc.headers and "Allow" in exc.headers:
            response.headers["Allow"] = exc.headers["Allow"]
        return response

    @application.exception_handler(WorkerError)
    async def domain_error(request: Request, exc: WorkerError) -> JSONResponse:
        status, message = {
            ErrorCode.INVALID_REQUEST: (422, "Request does not match the required schema."),
            ErrorCode.NOT_FOUND: (404, "Resource not found."),
            ErrorCode.INVALID_STATE: (409, "Operation is not valid in the current state."),
            ErrorCode.POLICY_BLOCKED: (403, "Operation blocked by policy."),
            ErrorCode.REQUEST_TOO_LARGE: (413, "Request body is too large."),
        }.get(exc.code, (500, "An internal error occurred."))
        return error_response(request, exc.code, message, status)

    @application.get("/api/v1/health/live", response_model=HealthResponse)
    async def live() -> HealthResponse:
        return HealthResponse(status="alive")

    @application.get(
        "/api/v1/health/ready",
        response_model=HealthResponse,
        responses={503: {"model": HealthResponse}},
    )
    def readiness(response: Response) -> HealthResponse:
        available = ready and store.ready() and knowledge.ready()
        if not available:
            response.status_code = 503
        return HealthResponse(status="ready" if available else "not_ready")

    return application
