from __future__ import annotations

import json
from pathlib import Path

from pyflow.models.a2a import AgentCard
from pyflow.models.workflow import SkillDef, WorkflowDef


class AgentCardGenerator:
    """Generates A2A agent-card.json from workflow definitions."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self._base_url = base_url.rstrip("/")

    def generate_card(self, workflow: WorkflowDef) -> AgentCard:
        """Generate an A2A agent card for a single workflow."""
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

    def generate_all(self, workflows: list[WorkflowDef]) -> list[AgentCard]:
        """Generate agent cards for all workflows."""
        return [self.generate_card(w) for w in workflows]

    def load_card(self, package_dir: Path) -> AgentCard:
        """Load an agent card from a package directory's agent-card.json."""
        card_path = package_dir / "agent-card.json"
        data = json.loads(card_path.read_text())
        return AgentCard.model_validate(data)

    def load_all(self, agents_dir: Path) -> list[AgentCard]:
        """Load agent cards from all agent package subdirectories."""
        cards = []
        for package_dir in sorted(agents_dir.iterdir()):
            card_path = package_dir / "agent-card.json"
            if package_dir.is_dir() and card_path.exists():
                cards.append(self.load_card(package_dir))
        return cards
