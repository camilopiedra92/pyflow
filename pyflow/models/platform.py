from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class PlatformConfig(BaseModel):
    """Global platform configuration."""

    tools_dir: str = "pyflow/tools"
    workflows_dir: str = "workflows"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    host: str = "0.0.0.0"
    port: int = Field(default=8000, ge=1, le=65535)
    secrets: dict[str, str] = Field(default_factory=dict)
