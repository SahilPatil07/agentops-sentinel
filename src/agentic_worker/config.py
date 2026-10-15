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
