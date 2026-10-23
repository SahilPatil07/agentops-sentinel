import os
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for name in tuple(os.environ):
        if name.startswith("WORKER_"):
            monkeypatch.delenv(name)
    monkeypatch.setenv("WORKER_DATABASE_PATH", str(tmp_path / "test.sqlite3"))
    monkeypatch.setenv("WORKER_VECTOR_STORE_PATH", str(tmp_path / "knowledge-index"))
