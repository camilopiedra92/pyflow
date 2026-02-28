from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from pyflow.models.workflow import SkillDef


class AgentCard(BaseModel):
    """A2A protocol agent card -- describes agent capabilities for discovery."""

    model_config = ConfigDict(populate_by_name=True)

    name: str
    description: str = ""
    url: str
    version: str = "1.0.0"
    protocol_version: str = Field(default="0.2.6", alias="protocolVersion")
    capabilities: dict = {}
    default_input_modes: list[str] = Field(
        default=["text/plain"], alias="defaultInputModes"
    )
    default_output_modes: list[str] = Field(
        default=["application/json"], alias="defaultOutputModes"
    )
    supports_authenticated_extended_card: bool = Field(
        default=False, alias="supportsAuthenticatedExtendedCard"
    )
    skills: list[SkillDef] = []
