from enum import StrEnum


class ErrorCode(StrEnum):
    INVALID_REQUEST = "invalid_request"
    NOT_FOUND = "not_found"
    INVALID_STATE = "invalid_state"
    POLICY_BLOCKED = "policy_blocked"
    REQUEST_TOO_LARGE = "request_too_large"
    HTTP_ERROR = "http_error"
    INTERNAL_ERROR = "internal_error"


class WorkerError(Exception):
    def __init__(self, code: ErrorCode) -> None:
        self.code = code
        super().__init__(code.value)
