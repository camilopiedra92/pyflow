from __future__ import annotations

from pyflow.models.a2a import AgentCard
from pyflow.models.workflow import SkillDef, WorkflowDef


class AgentCardGenerator:
    """Generates A2A agent cards from workflow definitions."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self._base_url = base_url.rstrip("/")

    def generate_card(self, workflow: WorkflowDef) -> AgentCard:
        """Build an AgentCard from a WorkflowDef."""
        skills: list[SkillDef] = []
        if workflow.a2a and workflow.a2a.skills:
            skills = list(workflow.a2a.skills)

        return AgentCard(
            name=workflow.name,
            description=workflow.description,
            url=f"{self._base_url}/a2a/{workflow.name}",
            version=workflow.a2a.version if workflow.a2a else "1.0.0",
            skills=skills,
        )

    def generate_cards(self, workflows: list[WorkflowDef]) -> list[AgentCard]:
        """Generate cards for A2A-enabled workflows (those with a2a: section)."""
        return [self.generate_card(w) for w in workflows if w.a2a is not None]
