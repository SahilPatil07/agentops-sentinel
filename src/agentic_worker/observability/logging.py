import json
import logging
import sys
from datetime import UTC, datetime


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        event = record.getMessage()
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "event": event
            if event in {"request_completed", "request_failed"}
            else "application_event",
            "stage": "http",
        }
        for field in ("request_id", "method", "route", "status_code", "duration_ms"):
            if field in record.__dict__:
                payload[field] = record.__dict__[field]
        return json.dumps(payload, ensure_ascii=True, allow_nan=False)


def configure_logging(level: str) -> None:
    logger = logging.getLogger("agentic_worker")
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
