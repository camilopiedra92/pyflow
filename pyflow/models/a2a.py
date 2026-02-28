from __future__ import annotations

from pydantic import BaseModel

from pyflow.models.workflow import SkillDef


class AgentCard(BaseModel):
    """A2A protocol agent card -- describes agent capabilities for discovery."""

    name: str
    description: str = ""
    url: str
    version: str = "1.0.0"
    protocol_version: str = "0.2.6"
    capabilities: dict = {}
    default_input_modes: list[str] = ["text/plain"]
    default_output_modes: list[str] = ["application/json"]
    supports_authenticated_extended_card: bool = False
    skills: list[SkillDef] = []
