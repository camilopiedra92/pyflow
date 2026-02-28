from __future__ import annotations

from pyflow.models.a2a import AgentCard, AgentCardSkill
from pyflow.models.workflow import WorkflowDef


class AgentCardGenerator:
    """Generates A2A agent-card.json from workflow definitions."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self._base_url = base_url.rstrip("/")

    def generate_card(self, workflow: WorkflowDef) -> AgentCard:
        """Generate an A2A agent card for a single workflow."""
        skills: list[AgentCardSkill] = []
        if workflow.a2a and workflow.a2a.skills:
            skills = [
                AgentCardSkill(
                    id=skill.id,
                    name=skill.name,
                    description=skill.description,
                    tags=skill.tags,
                )
                for skill in workflow.a2a.skills
            ]

        return AgentCard(
            name=workflow.name,
            description=workflow.description,
            url=f"{self._base_url}/a2a/{workflow.name}",
            version=workflow.a2a.version if workflow.a2a else "1.0.0",
            skills=skills,
        )

    def generate_all(self, workflows: list[WorkflowDef]) -> list[AgentCard]:
        """Generate agent cards for all workflows."""
        return [self.generate_card(w) for w in workflows]
