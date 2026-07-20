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

    cad_kernel: Literal["cadquery", "freecad"] = "cadquery"
    generation_mode: Literal["script", "agent"] = "script"
    freecad_agent_backend: Literal["worker", "replay"] = "worker"
    image_input_enabled: bool = False
    image_max_upload_bytes: int = Field(default=5 * 1024 * 1024, ge=1024, le=25 * 1024 * 1024)
    image_max_count_per_message: int = Field(default=4, ge=1, le=10)
    image_allowed_content_types: list[str] = [
        "image/png",
        "image/jpeg",
        "image/webp",
    ]

    llm_provider: Literal[
        "mock",
        "openai",
        "anthropic",
        "deepseek",
        "openai_compatible",
    ] = "mock"
    llm_max_tokens: int = Field(default=8000, ge=512, le=64000)
    generation_max_repair_attempts: int = Field(default=2, ge=0, le=5)

    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1"

    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-4-5"
    anthropic_agent_prompt_cache: bool = False
    anthropic_agent_prompt_cache_ttl: Literal["5m", "1h"] = "5m"

    deepseek_api_key: str | None = None
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-v4-flash"
    deepseek_supports_images: bool = False

    openai_compatible_api_key: str | None = None
    openai_compatible_base_url: str | None = None
    openai_compatible_model: str | None = None
    openai_compatible_supports_images: bool = False

    cad_runner_timeout_seconds: int = Field(default=90, ge=5, le=600)
    cad_runner_python: str | None = None
    cad_runner_script: Path | None = None
    freecad_python: str | None = None
    freecad_runner_script: Path | None = None
    freecad_gui_executable: str | None = None
    freecad_worker_script: Path | None = None
    freecad_worker_view_backend: Literal["summary", "gui", "pyvista", "solid"] = "summary"
    freecad_worker_timeout_seconds: int = Field(default=60, ge=5, le=600)
    freecad_session_idle_timeout_seconds: int = Field(default=900, ge=60, le=7200)
    agent_max_tool_calls: int = Field(default=30, ge=1, le=100)
    agent_max_runtime_seconds: int = Field(default=300, ge=30, le=1800)
    agent_max_code_chars: int = Field(default=12000, ge=1000, le=50000)

    cors_origins: list[str] = [
        "http://localhost:4200",
        "http://127.0.0.1:4200",
    ]

    @field_validator(
        "cad_runner_python",
        "cad_runner_script",
        "freecad_python",
        "freecad_runner_script",
        "freecad_gui_executable",
        "freecad_worker_script",
        "deepseek_api_key",
        "openai_compatible_api_key",
        "openai_compatible_base_url",
        "openai_compatible_model",
        mode="before",
    )
    @classmethod
    def empty_string_to_none(cls, value):
        if isinstance(value, str) and not value.strip():
            return None
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
