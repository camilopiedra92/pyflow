from __future__ import annotations

import pytest
from pydantic import ValidationError

from pyflow.models.agent import AgentConfig
from pyflow.models.workflow import (
    A2AConfig,
    DagNode,
    OrchestrationConfig,
    RuntimeConfig,
    SkillDef,
    WorkflowDef,
)


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


class TestRuntimeConfig:
    def test_defaults(self):
        config = RuntimeConfig()
        assert config.session_service == "in_memory"
        assert config.session_db_url is None
        assert config.memory_service == "none"
        assert config.artifact_service == "none"
        assert config.artifact_dir is None
        assert config.plugins == []

    def test_all_fields(self):
        config = RuntimeConfig(
            session_service="sqlite",
            session_db_url="sqlite+aiosqlite:///test.db",
            memory_service="in_memory",
            artifact_service="file",
            artifact_dir="./artifacts",
            plugins=["logging", "reflect_and_retry"],
        )
        assert config.session_service == "sqlite"
        assert config.memory_service == "in_memory"
        assert config.artifact_service == "file"
        assert config.plugins == ["logging", "reflect_and_retry"]

    def test_invalid_session_service(self):
        with pytest.raises(ValidationError):
            RuntimeConfig(session_service="redis")

    def test_invalid_memory_service(self):
        with pytest.raises(ValidationError):
            RuntimeConfig(memory_service="redis")

    def test_invalid_artifact_service(self):
        with pytest.raises(ValidationError):
            RuntimeConfig(artifact_service="s3")


class TestDagNode:
    def test_minimal(self):
        node = DagNode(agent="fetcher")
        assert node.agent == "fetcher"
        assert node.depends_on == []

    def test_with_dependencies(self):
        node = DagNode(agent="merger", depends_on=["a", "b"])
        assert node.depends_on == ["a", "b"]


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
                model="gemini-2.5-flash",
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
            orchestration=OrchestrationConfig(type="sequential", agents=["fetcher", "analyzer"]),
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
            orchestration=OrchestrationConfig(type="sequential", agents=["fetcher", "analyzer"]),
            a2a=A2AConfig(skills=[SkillDef(id="rate", name="Rate Tracking")]),
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
            orchestration=OrchestrationConfig(type="sequential", agents=["fetcher", "analyzer"]),
        )
        assert wf.description == ""

    def test_workflow_def_default_runtime(self):
        """Existing WorkflowDef should work with default RuntimeConfig."""
        agents = self._make_agents()
        wf = WorkflowDef(
            name="with_default_runtime",
            agents=agents,
            orchestration=OrchestrationConfig(type="sequential", agents=["fetcher", "analyzer"]),
        )
        assert wf.runtime is not None
        assert wf.runtime.session_service == "in_memory"
        assert wf.runtime.memory_service == "none"

    def test_workflow_def_with_runtime(self):
        """WorkflowDef with custom runtime config."""
        agents = self._make_agents()
        wf = WorkflowDef(
            name="custom_runtime",
            agents=agents,
            orchestration=OrchestrationConfig(type="sequential", agents=["fetcher", "analyzer"]),
            runtime=RuntimeConfig(
                session_service="sqlite",
                session_db_url="sqlite+aiosqlite:///wf.db",
                memory_service="in_memory",
                artifact_service="file",
                artifact_dir="./artifacts",
            ),
        )
        assert wf.runtime.session_service == "sqlite"
        assert wf.runtime.artifact_service == "file"

    def test_orchestration_refs_dag_validates_node_agents(self):
        """WorkflowDef validator checks dag node agent refs against defined agents."""
        agents = self._make_agents()
        with pytest.raises(ValidationError, match="unknown_agent"):
            WorkflowDef(
                name="bad_dag",
                agents=agents,
                orchestration=OrchestrationConfig(
                    type="dag",
                    nodes=[
                        DagNode(agent="fetcher"),
                        DagNode(agent="unknown_agent", depends_on=["fetcher"]),
                    ],
                ),
            )

    def test_orchestration_refs_react_validates_agent(self):
        """WorkflowDef validator checks react agent ref against defined agents."""
        agents = self._make_agents()
        with pytest.raises(ValidationError, match="nonexistent"):
            WorkflowDef(
                name="bad_react",
                agents=agents,
                orchestration=OrchestrationConfig(
                    type="react",
                    agent="nonexistent",
                ),
            )

    def test_orchestration_refs_llm_routed_validates_router(self):
        """WorkflowDef validator checks llm_routed router ref against defined agents."""
        agents = self._make_agents()
        with pytest.raises(ValidationError, match="bad_router"):
            WorkflowDef(
                name="bad_routed",
                agents=agents,
                orchestration=OrchestrationConfig(
                    type="llm_routed",
                    router="bad_router",
                    agents=["fetcher", "analyzer"],
                ),
            )

    def test_orchestration_refs_llm_routed_validates_agents(self):
        """WorkflowDef validator checks llm_routed agents refs against defined agents."""
        agents = self._make_agents()
        with pytest.raises(ValidationError, match="missing_agent"):
            WorkflowDef(
                name="bad_routed",
                agents=agents,
                orchestration=OrchestrationConfig(
                    type="llm_routed",
                    router="fetcher",
                    agents=["missing_agent"],
                ),
            )

    def test_workflow_dag_valid(self):
        """WorkflowDef with valid dag orchestration passes all validation."""
        agents = self._make_agents()
        wf = WorkflowDef(
            name="dag_wf",
            agents=agents,
            orchestration=OrchestrationConfig(
                type="dag",
                nodes=[
                    DagNode(agent="fetcher"),
                    DagNode(agent="analyzer", depends_on=["fetcher"]),
                ],
            ),
        )
        assert wf.orchestration.type == "dag"

    def test_workflow_react_valid(self):
        """WorkflowDef with valid react orchestration passes all validation."""
        agents = self._make_agents()
        wf = WorkflowDef(
            name="react_wf",
            agents=agents,
            orchestration=OrchestrationConfig(
                type="react",
                agent="fetcher",
            ),
        )
        assert wf.orchestration.type == "react"

    def test_workflow_llm_routed_valid(self):
        """WorkflowDef with valid llm_routed orchestration passes all validation."""
        agents = self._make_agents()
        wf = WorkflowDef(
            name="routed_wf",
            agents=agents,
            orchestration=OrchestrationConfig(
                type="llm_routed",
                router="fetcher",
                agents=["fetcher", "analyzer"],
            ),
        )
        assert wf.orchestration.type == "llm_routed"


class TestOrchestrationConfigExpanded:
    """Tests for expanded orchestration types: react, dag, llm_routed."""

    def test_react(self):
        config = OrchestrationConfig(type="react", agent="reasoner", planner="plan_react")
        assert config.type == "react"
        assert config.agent == "reasoner"
        assert config.planner == "plan_react"

    def test_react_requires_agent(self):
        with pytest.raises(ValidationError):
            OrchestrationConfig(type="react")

    def test_dag(self):
        config = OrchestrationConfig(
            type="dag",
            nodes=[
                DagNode(agent="a"),
                DagNode(agent="b", depends_on=["a"]),
            ],
        )
        assert config.type == "dag"
        assert len(config.nodes) == 2

    def test_dag_requires_nodes(self):
        with pytest.raises(ValidationError):
            OrchestrationConfig(type="dag")

    def test_dag_detects_cycle(self):
        with pytest.raises(ValidationError, match="cycle"):
            OrchestrationConfig(
                type="dag",
                nodes=[
                    DagNode(agent="a", depends_on=["b"]),
                    DagNode(agent="b", depends_on=["a"]),
                ],
            )

    def test_dag_detects_self_cycle(self):
        with pytest.raises(ValidationError, match="cycle"):
            OrchestrationConfig(
                type="dag",
                nodes=[DagNode(agent="a", depends_on=["a"])],
            )

    def test_dag_detects_three_node_cycle(self):
        with pytest.raises(ValidationError, match="cycle"):
            OrchestrationConfig(
                type="dag",
                nodes=[
                    DagNode(agent="a", depends_on=["c"]),
                    DagNode(agent="b", depends_on=["a"]),
                    DagNode(agent="c", depends_on=["b"]),
                ],
            )

    def test_dag_unknown_dependency(self):
        with pytest.raises(ValidationError, match="Unknown dependency"):
            OrchestrationConfig(
                type="dag",
                nodes=[DagNode(agent="a", depends_on=["nonexistent"])],
            )

    def test_dag_valid_diamond(self):
        """Diamond-shaped DAG (a -> b, a -> c, b -> d, c -> d) is acyclic."""
        config = OrchestrationConfig(
            type="dag",
            nodes=[
                DagNode(agent="a"),
                DagNode(agent="b", depends_on=["a"]),
                DagNode(agent="c", depends_on=["a"]),
                DagNode(agent="d", depends_on=["b", "c"]),
            ],
        )
        assert len(config.nodes) == 4

    def test_llm_routed(self):
        config = OrchestrationConfig(type="llm_routed", router="dispatcher", agents=["a", "b"])
        assert config.type == "llm_routed"
        assert config.router == "dispatcher"

    def test_llm_routed_requires_router_and_agents(self):
        with pytest.raises(ValidationError):
            OrchestrationConfig(type="llm_routed", router="dispatcher")
        with pytest.raises(ValidationError):
            OrchestrationConfig(type="llm_routed", agents=["a"])

    def test_loop_with_max_iterations(self):
        config = OrchestrationConfig(type="loop", agents=["a", "b"], max_iterations=5)
        assert config.max_iterations == 5

    def test_sequential_still_works(self):
        config = OrchestrationConfig(type="sequential", agents=["a", "b"])
        assert config.type == "sequential"
        assert config.agents == ["a", "b"]

    def test_parallel_still_works(self):
        config = OrchestrationConfig(type="parallel", agents=["a", "b"])
        assert config.type == "parallel"
        assert config.agents == ["a", "b"]

    def test_sequential_requires_agents(self):
        with pytest.raises(ValidationError):
            OrchestrationConfig(type="sequential")

    def test_parallel_requires_agents(self):
        with pytest.raises(ValidationError):
            OrchestrationConfig(type="parallel")

    def test_loop_requires_agents(self):
        with pytest.raises(ValidationError):
            OrchestrationConfig(type="loop")
