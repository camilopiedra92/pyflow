from __future__ import annotations

import pytest

from pyflow.models.a2a import AgentCard
from pyflow.models.workflow import SkillDef


class TestSkillDef:
    def test_creation_with_all_fields(self):
        skill = SkillDef(
            id="summarize",
            name="Summarize",
            description="Summarizes text",
            tags=["nlp", "text"],
        )
        assert skill.id == "summarize"
        assert skill.name == "Summarize"
        assert skill.description == "Summarizes text"
        assert skill.tags == ["nlp", "text"]

    def test_defaults(self):
        skill = SkillDef(id="skill_1", name="Skill One")
        assert skill.description == ""
        assert skill.tags == []

    def test_id_required(self):
        with pytest.raises(Exception):
            SkillDef(name="missing_id")

    def test_name_required(self):
        with pytest.raises(Exception):
            SkillDef(id="missing_name")

    def test_serialization(self):
        skill = SkillDef(id="s1", name="S1", description="desc", tags=["a"])
        data = skill.model_dump()
        assert data == {"id": "s1", "name": "S1", "description": "desc", "tags": ["a"]}


class TestAgentCard:
    def test_creation_with_all_fields(self):
        card = AgentCard(
            name="my_agent",
            description="Does things",
            url="http://localhost:8000/a2a/my_agent",
            version="2.0.0",
            protocol_version="0.3.0",
            capabilities={"streaming": True},
            default_input_modes=["application/json"],
            default_output_modes=["text/plain"],
            supports_authenticated_extended_card=True,
            skills=[
                SkillDef(id="s1", name="Skill 1"),
            ],
        )
        assert card.name == "my_agent"
        assert card.description == "Does things"
        assert card.url == "http://localhost:8000/a2a/my_agent"
        assert card.version == "2.0.0"
        assert card.protocol_version == "0.3.0"
        assert card.capabilities == {"streaming": True}
        assert card.default_input_modes == ["application/json"]
        assert card.default_output_modes == ["text/plain"]
        assert card.supports_authenticated_extended_card is True
        assert len(card.skills) == 1
        assert card.skills[0].id == "s1"

    def test_defaults(self):
        card = AgentCard(name="agent", url="http://localhost:8000")
        assert card.description == ""
        assert card.version == "1.0.0"
        assert card.protocol_version == "0.2.6"
        assert card.capabilities == {}
        assert card.default_input_modes == ["text/plain"]
        assert card.default_output_modes == ["application/json"]
        assert card.supports_authenticated_extended_card is False
        assert card.skills == []

    def test_name_required(self):
        with pytest.raises(Exception):
            AgentCard(url="http://localhost:8000")

    def test_url_required(self):
        with pytest.raises(Exception):
            AgentCard(name="agent")

    def test_serialization(self):
        card = AgentCard(
            name="agent",
            url="http://localhost:8000",
            skills=[SkillDef(id="s1", name="S1")],
        )
        data = card.model_dump()
        assert data["name"] == "agent"
        assert data["url"] == "http://localhost:8000"
        assert len(data["skills"]) == 1
        assert data["skills"][0]["id"] == "s1"
