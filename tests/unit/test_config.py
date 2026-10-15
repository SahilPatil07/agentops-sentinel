from pathlib import Path

import pytest
from pydantic import ValidationError

from agentic_worker.config import Settings


def test_environment_overrides_dotenv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text("WORKER_LOG_LEVEL=WARNING\n", encoding="utf-8")
    monkeypatch.setenv("WORKER_LOG_LEVEL", "ERROR")
    assert Settings(_env_file=dotenv).log_level == "ERROR"
    monkeypatch.delenv("WORKER_LOG_LEVEL")
    assert Settings(_env_file=dotenv).log_level == "WARNING"


@pytest.mark.parametrize("value", ["0", "-1", "1048577", "not-a-number"])
def test_invalid_limits(value: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WORKER_MAX_REQUEST_BYTES", value)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_unknown_settings_rejected(tmp_path: Path) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text("WORKER_LOG_LEVLE=DEBUG\n", encoding="utf-8")
    with pytest.raises(ValidationError):
        Settings(_env_file=dotenv)


def test_unsupported_environment_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WORKER_ENVIRONMENT", "production")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)
