from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from agentic_worker.api.middleware import RequestBoundaryMiddleware
from agentic_worker.api.schemas import ErrorResponse, HealthResponse
from agentic_worker.config import Settings
from agentic_worker.domain.errors import ErrorCode, WorkerError
from agentic_worker.observability.logging import configure_logging


def create_app(settings: Settings | None = None) -> FastAPI:
    configuration = settings if settings is not None else Settings()
    ready = False

    @asynccontextmanager
    async def lifespan(_application: FastAPI) -> AsyncIterator[None]:
        nonlocal ready
        configure_logging(configuration.log_level)
        ready = True
        try:
            yield
        finally:
            ready = False

    application = FastAPI(
        title="Enterprise Digital Worker",
        version="0.1.0",
        debug=False,
        lifespan=lifespan,
        responses={
            status: {"model": ErrorResponse} for status in (400, 403, 404, 409, 413, 422, 500)
        },
    )
    application.state.settings = configuration
    application.add_middleware(RequestBoundaryMiddleware, settings=configuration)

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
    async def readiness(response: Response) -> HealthResponse:
        if not ready:
            response.status_code = 503
        return HealthResponse(status="ready" if ready else "not_ready")

    return application
