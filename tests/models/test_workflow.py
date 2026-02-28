from __future__ import annotations

import pytest
from pydantic import ValidationError

from pyflow.models.agent import AgentConfig
from pyflow.models.workflow import A2AConfig, OrchestrationConfig, SkillDef, WorkflowDef


class TestSkillDef:
    def test_creation(self):
        skill = SkillDef(id="rate_tracking", name="Exchange Rate Tracking")
        assert skill.id == "rate_tracking"
        assert skill.name == "Exchange Rate Tracking"
        assert skill.description == ""
        assert skill.tags == []

    def test_with_all_fields(self):
        skill = SkillDef(
            id="rate_tracking",
            name="Exchange Rate Tracking",
            description="Track exchange rates",
            tags=["finance", "monitoring"],
        )
        assert skill.description == "Track exchange rates"
        assert skill.tags == ["finance", "monitoring"]


class TestA2AConfig:
    def test_defaults(self):
        a2a = A2AConfig()
        assert a2a.version == "1.0.0"
        assert a2a.skills == []

    def test_with_skills(self):
        a2a = A2AConfig(
            version="2.0.0",
            skills=[SkillDef(id="s1", name="Skill One")],
        )
        assert a2a.version == "2.0.0"
        assert len(a2a.skills) == 1


class TestOrchestrationConfig:
    def test_sequential(self):
        orch = OrchestrationConfig(type="sequential", agents=["a", "b"])
        assert orch.type == "sequential"
        assert orch.agents == ["a", "b"]

    def test_parallel(self):
        orch = OrchestrationConfig(type="parallel", agents=["x", "y", "z"])
        assert orch.type == "parallel"

    def test_loop(self):
        orch = OrchestrationConfig(type="loop", agents=["worker"])
        assert orch.type == "loop"

    def test_invalid_type(self):
        with pytest.raises(ValidationError):
            OrchestrationConfig(type="invalid", agents=["a"])


class TestWorkflowDef:
    def _make_agents(self):
        return [
            AgentConfig(
                name="fetcher",
                type="llm",
                model="gemini-2.0-flash",
                instruction="Fetch data",
                tools=["http_request"],
            ),
            AgentConfig(
                name="analyzer",
                type="llm",
                model="anthropic/claude-sonnet-4-20250514",
                instruction="Analyze data",
                tools=["condition"],
            ),
        ]

    def test_valid_workflow(self):
        agents = self._make_agents()
        wf = WorkflowDef(
            name="exchange_tracker",
            description="Track exchange rates",
            agents=agents,
            orchestration=OrchestrationConfig(
                type="sequential", agents=["fetcher", "analyzer"]
            ),
        )
        assert wf.name == "exchange_tracker"
        assert wf.description == "Track exchange rates"
        assert len(wf.agents) == 2
        assert wf.a2a is None

    def test_with_a2a_config(self):
        agents = self._make_agents()
        wf = WorkflowDef(
            name="exchange_tracker",
            agents=agents,
            orchestration=OrchestrationConfig(
                type="sequential", agents=["fetcher", "analyzer"]
            ),
            a2a=A2AConfig(
                skills=[SkillDef(id="rate", name="Rate Tracking")]
            ),
        )
        assert wf.a2a is not None
        assert len(wf.a2a.skills) == 1

    def test_orchestration_refs_must_match_agents(self):
        agents = self._make_agents()
        with pytest.raises(ValidationError, match="nonexistent"):
            WorkflowDef(
                name="bad",
                agents=agents,
                orchestration=OrchestrationConfig(
                    type="sequential", agents=["fetcher", "nonexistent"]
                ),
            )

    def test_description_defaults_to_empty(self):
        agents = self._make_agents()
        wf = WorkflowDef(
            name="minimal",
            agents=agents,
            orchestration=OrchestrationConfig(
                type="sequential", agents=["fetcher", "analyzer"]
            ),
        )
        assert wf.description == ""
