from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="WORKER_", env_file=".env", env_file_encoding="utf-8", extra="forbid"
    )

    environment: Literal["local", "test"] = "local"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    max_request_bytes: int = Field(default=65_536, ge=1_024, le=1_048_576)
    database_path: str = Field(default="agentops.sqlite3", min_length=1, max_length=500)
    max_graph_steps: int = Field(default=8, ge=1, le=32)
    max_tool_calls: int = Field(default=8, ge=1, le=16)
    tool_timeout_seconds: float = Field(default=2.0, gt=0, le=30, allow_inf_nan=False)
    provider_timeout_seconds: float = Field(default=5.0, gt=0, le=60, allow_inf_nan=False)
    workflow_timeout_seconds: float = Field(default=30.0, gt=0, le=120, allow_inf_nan=False)
    max_provider_attempts: int = Field(default=2, ge=1, le=3)
    max_tool_output_bytes: int = Field(default=16_384, ge=256, le=65_536)
    max_report_bytes: int = Field(default=65_536, ge=256, le=131_072)
    knowledge_path: str = Field(default="knowledge", min_length=1, max_length=500)
    vector_store_path: str = Field(default="knowledge-index", min_length=1, max_length=500)
    retrieval_top_k: int = Field(default=2, ge=1, le=8)
    retrieval_min_score: float = Field(default=0.12, ge=0, le=1, allow_inf_nan=False)
    retrieval_timeout_seconds: float = Field(default=3.0, gt=0, le=30, allow_inf_nan=False)
