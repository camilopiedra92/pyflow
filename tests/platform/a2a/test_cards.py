from __future__ import annotations

import json
from pathlib import Path

from pyflow.models.a2a import AgentCard
from pyflow.models.workflow import SkillDef
from pyflow.models.agent import AgentConfig
from pyflow.models.workflow import A2AConfig, OrchestrationConfig, WorkflowDef
from pyflow.platform.a2a.cards import AgentCardGenerator


def _minimal_workflow(name: str = "test_wf", *, a2a: A2AConfig | None = None) -> WorkflowDef:
    """Create a minimal valid workflow for testing."""
    return WorkflowDef(
        name=name,
        description=f"Description for {name}",
        agents=[
            AgentConfig(
                name="agent1",
                type="llm",
                model="gemini-2.5-flash",
                instruction="Do something",
            ),
        ],
        orchestration=OrchestrationConfig(type="sequential", agents=["agent1"]),
        a2a=a2a,
    )


class TestGenerateCardBasic:
    def test_generate_card_basic(self) -> None:
        """Minimal workflow with no a2a config produces a card with defaults."""
        gen = AgentCardGenerator()
        wf = _minimal_workflow()
        card = gen.generate_card(wf)

        assert isinstance(card, AgentCard)
        assert card.name == "test_wf"
        assert card.description == "Description for test_wf"
        assert card.version == "1.0.0"
        assert card.protocol_version == "0.2.6"
        assert card.skills == []

    def test_generate_card_with_a2a_config(self) -> None:
        """Workflow with a2a.version and skills reflects them in the card."""
        a2a = A2AConfig(
            version="2.5.0",
            skills=[
                SkillDef(
                    id="rate_tracking",
                    name="Exchange Rate Tracking",
                    description="Track exchange rates",
                    tags=["finance", "monitoring"],
                ),
            ],
        )
        gen = AgentCardGenerator()
        wf = _minimal_workflow(a2a=a2a)
        card = gen.generate_card(wf)

        assert card.version == "2.5.0"
        assert len(card.skills) == 1
        assert card.skills[0].id == "rate_tracking"
        assert card.skills[0].name == "Exchange Rate Tracking"
        assert card.skills[0].description == "Track exchange rates"
        assert card.skills[0].tags == ["finance", "monitoring"]


class TestCardUrl:
    def test_generate_card_url_format(self) -> None:
        """URL follows {base_url}/a2a/{name} pattern."""
        gen = AgentCardGenerator()
        wf = _minimal_workflow(name="my_workflow")
        card = gen.generate_card(wf)

        assert card.url == "http://localhost:8000/a2a/my_workflow"

    def test_generate_card_custom_base_url(self) -> None:
        """Custom base_url is reflected in the card URL."""
        gen = AgentCardGenerator(base_url="https://prod.example.com:9000")
        wf = _minimal_workflow(name="wf1")
        card = gen.generate_card(wf)

        assert card.url == "https://prod.example.com:9000/a2a/wf1"

    def test_generate_card_strips_trailing_slash(self) -> None:
        """Trailing slash on base_url does not cause double slash in URL."""
        gen = AgentCardGenerator(base_url="http://example.com/")
        wf = _minimal_workflow(name="wf2")
        card = gen.generate_card(wf)

        assert card.url == "http://example.com/a2a/wf2"
        assert "//" not in card.url.split("://")[1]


class TestGenerateAll:
    def test_generate_all_multiple_workflows(self) -> None:
        """generate_all returns a card for each workflow."""
        gen = AgentCardGenerator()
        workflows = [_minimal_workflow(f"wf_{i}") for i in range(3)]
        cards = gen.generate_all(workflows)

        assert len(cards) == 3
        assert [c.name for c in cards] == ["wf_0", "wf_1", "wf_2"]

    def test_generate_all_empty_list(self) -> None:
        """Empty input yields empty output."""
        gen = AgentCardGenerator()
        assert gen.generate_all([]) == []


class TestCardStructure:
    def test_card_has_required_a2a_fields(self) -> None:
        """Every generated card contains all required A2A protocol fields."""
        gen = AgentCardGenerator()
        card = gen.generate_card(_minimal_workflow())

        required_attrs = [
            "name",
            "url",
            "version",
            "protocol_version",
            "capabilities",
            "default_input_modes",
            "default_output_modes",
            "skills",
        ]
        for attr in required_attrs:
            assert hasattr(card, attr), f"Missing required attribute: {attr}"

    def test_skills_structure(self) -> None:
        """Each skill entry has the required id, name, description, tags."""
        a2a = A2AConfig(
            skills=[
                SkillDef(id="s1", name="Skill One", description="First", tags=["a"]),
                SkillDef(id="s2", name="Skill Two", description="Second", tags=["b", "c"]),
            ],
        )
        gen = AgentCardGenerator()
        card = gen.generate_card(_minimal_workflow(a2a=a2a))

        assert len(card.skills) == 2
        for skill in card.skills:
            assert isinstance(skill, SkillDef)
            assert skill.id
            assert skill.name
            assert skill.description
            assert isinstance(skill.tags, list)


class TestLoadCard:
    def test_load_card_from_json(self, tmp_path: Path) -> None:
        """load_card() reads agent-card.json from a package directory."""
        card_data = {
            "name": "test_agent",
            "description": "Test agent",
            "url": "http://localhost:8000/a2a/test_agent",
            "version": "1.0.0",
            "skills": [],
        }
        (tmp_path / "agent-card.json").write_text(json.dumps(card_data))

        gen = AgentCardGenerator()
        card = gen.load_card(tmp_path)

        assert isinstance(card, AgentCard)
        assert card.name == "test_agent"
        assert card.url == "http://localhost:8000/a2a/test_agent"

    def test_load_card_with_skills(self, tmp_path: Path) -> None:
        """load_card() deserializes skills from JSON."""
        card_data = {
            "name": "skilled_agent",
            "description": "Has skills",
            "url": "http://localhost:8000/a2a/skilled_agent",
            "version": "2.0.0",
            "skills": [
                {"id": "s1", "name": "Skill One", "description": "First", "tags": ["a"]},
            ],
        }
        (tmp_path / "agent-card.json").write_text(json.dumps(card_data))

        gen = AgentCardGenerator()
        card = gen.load_card(tmp_path)

        assert card.version == "2.0.0"
        assert len(card.skills) == 1
        assert card.skills[0].id == "s1"


class TestLoadAll:
    def test_load_all_from_agent_packages(self, tmp_path: Path) -> None:
        """load_all() loads cards from all agent package subdirs."""
        for name in ["agent_a", "agent_b"]:
            pkg = tmp_path / name
            pkg.mkdir()
            card_data = {
                "name": name,
                "description": f"Desc {name}",
                "url": f"http://localhost/{name}",
                "skills": [],
            }
            (pkg / "agent-card.json").write_text(json.dumps(card_data))

        gen = AgentCardGenerator()
        cards = gen.load_all(tmp_path)

        assert len(cards) == 2
        assert [c.name for c in cards] == ["agent_a", "agent_b"]

    def test_load_all_skips_dirs_without_card(self, tmp_path: Path) -> None:
        """load_all() ignores subdirectories without agent-card.json."""
        pkg = tmp_path / "has_card"
        pkg.mkdir()
        (pkg / "agent-card.json").write_text(
            json.dumps({"name": "has_card", "description": "", "url": "http://x", "skills": []})
        )

        no_card = tmp_path / "no_card"
        no_card.mkdir()

        gen = AgentCardGenerator()
        cards = gen.load_all(tmp_path)
        assert len(cards) == 1
        assert cards[0].name == "has_card"

    def test_load_all_empty_dir(self, tmp_path: Path) -> None:
        """Empty directory returns empty list."""
        gen = AgentCardGenerator()
        assert gen.load_all(tmp_path) == []
