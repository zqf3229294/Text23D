from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TEXT23D_",
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_path: Path = Path("data/text23d.sqlite3")
    storage_dir: Path = Path("data/artifacts")

    llm_provider: Literal["mock", "openai", "anthropic"] = "mock"
    generation_max_repair_attempts: int = Field(default=2, ge=0, le=5)

    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1"

    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-4-5"

    cad_runner_timeout_seconds: int = Field(default=90, ge=5, le=600)
    cad_runner_python: str | None = None
    cad_runner_script: Path | None = None

    cors_origins: list[str] = [
        "http://localhost:4200",
        "http://127.0.0.1:4200",
    ]

    @field_validator("cad_runner_python", "cad_runner_script", mode="before")
    @classmethod
    def empty_string_to_none(cls, value):
        if isinstance(value, str) and not value.strip():
            return None
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
