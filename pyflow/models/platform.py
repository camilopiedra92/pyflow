from __future__ import annotations

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class PlatformConfig(BaseSettings):
    """Global platform configuration.

    Reads from environment variables with PYFLOW_ prefix and .env files.
    """

    model_config = SettingsConfigDict(
        env_prefix="PYFLOW_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    tools_dir: str = "pyflow/tools"
    workflows_dir: str = "workflows"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    host: str = "0.0.0.0"
    port: int = Field(default=8000, ge=1, le=65535)
    secrets: dict[str, str] = Field(default_factory=dict)
