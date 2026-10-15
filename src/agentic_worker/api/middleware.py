import logging
from time import perf_counter
from uuid import uuid4

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from agentic_worker.api.schemas import ErrorResponse
from agentic_worker.config import Settings
from agentic_worker.domain.errors import ErrorCode

logger = logging.getLogger("agentic_worker.http")


class RequestBoundaryMiddleware:
    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        self.app = app
        self.max_request_bytes = settings.max_request_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = str(uuid4())
        scope.setdefault("state", {})["request_id"] = request_id
        started = perf_counter()
        status_code = 500
        response_started = False

        async def correlated_send(message: Message) -> None:
            nonlocal status_code, response_started
            if message["type"] == "http.response.start":
                status_code = message["status"]
                response_started = True
                headers = [
                    (name, value)
                    for name, value in message.get("headers", [])
                    if name.lower() != b"x-request-id"
                ]
                message = {
                    **message,
                    "headers": [*headers, (b"x-request-id", request_id.encode("ascii"))],
                }
            await send(message)

        async def reject(code: ErrorCode, status: int, message: str) -> None:
            payload = ErrorResponse(code=code, message=message, request_id=request_id)
            response = JSONResponse(payload.model_dump(mode="json"), status_code=status)
            await response(scope, receive, correlated_send)

        try:
            for name, value in scope["headers"]:
                if name.lower() == b"content-length":
                    if not value.isdigit() or len(value) > 16:
                        await reject(ErrorCode.INVALID_REQUEST, 400, "Invalid request framing.")
                        return
                    if int(value) > self.max_request_bytes:
                        await reject(ErrorCode.REQUEST_TOO_LARGE, 413, "Request body is too large.")
                        return

            chunks: list[bytes] = []
            size = 0
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    status_code = 499
                    return
                chunk = message.get("body", b"")
                size += len(chunk)
                if size > self.max_request_bytes:
                    await reject(ErrorCode.REQUEST_TOO_LARGE, 413, "Request body is too large.")
                    return
                chunks.append(chunk)
                if not message.get("more_body", False):
                    break

            body = b"".join(chunks)
            delivered = False

            async def buffered_receive() -> Message:
                nonlocal delivered
                if not delivered:
                    delivered = True
                    return {"type": "http.request", "body": body, "more_body": False}
                return await receive()

            await self.app(scope, buffered_receive, correlated_send)
        except Exception:
            status_code = 500
            if response_started:
                raise RuntimeError("Response failed after headers were sent.") from None
            await reject(ErrorCode.INTERNAL_ERROR, 500, "An internal error occurred.")
        finally:
            method = scope.get("method", "OTHER")
            if method not in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}:
                method = "OTHER"
            logger.log(
                logging.ERROR if status_code >= 500 else logging.INFO,
                "request_failed" if status_code >= 500 else "request_completed",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "route": getattr(scope.get("route"), "path", "unmatched"),
                    "status_code": status_code,
                    "duration_ms": round((perf_counter() - started) * 1000, 3),
                },
            )
