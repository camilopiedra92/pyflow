"""End-to-end tests for the budget_analyst agent package.

Simulates the real user flow: boot the platform, call run_workflow() with a
natural language message, and verify the agent responds with a budget analysis.

The Gemini LLM and YNAB API are mocked at the ADK Runner layer so the full
PyFlow pipeline executes for real — YAML loading, OpenAPI spec parsing,
ToolRegistry registration, hydration, executor session creation, datetime
injection, plugin wiring, event collection, and result building.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from google.adk.events import Event
from google.adk.runners import Runner
from google.genai import types

from pyflow.models.platform import PlatformConfig
from pyflow.platform.app import PyFlowPlatform


# ---------------------------------------------------------------------------
# Realistic YNAB API response fixtures
# ---------------------------------------------------------------------------

YNAB_BUDGETS_RESPONSE = {
    "data": {
        "budgets": [
            {
                "id": "budget-001",
                "name": "My Household Budget",
                "last_modified_on": "2026-02-28T10:00:00+00:00",
                "currency_format": {
                    "iso_code": "USD",
                    "decimal_digits": 2,
                    "decimal_separator": ".",
                    "symbol_first": True,
                    "currency_symbol": "$",
                },
            }
        ]
    }
}

YNAB_TRANSACTIONS_RESPONSE = {
    "data": {
        "transactions": [
            {
                "id": "txn-001",
                "date": "2026-02-15",
                "amount": -52340,
                "memo": "Weekly groceries",
                "payee_name": "Whole Foods",
                "category_name": "Groceries",
                "account_name": "Chase Checking",
                "cleared": "cleared",
            },
            {
                "id": "txn-002",
                "date": "2026-02-20",
                "amount": -31200,
                "memo": "Fresh produce",
                "payee_name": "Trader Joe's",
                "category_name": "Groceries",
                "account_name": "Chase Checking",
                "cleared": "cleared",
            },
            {
                "id": "txn-003",
                "date": "2026-02-22",
                "amount": -15800,
                "memo": "Lunch supplies",
                "payee_name": "Costco",
                "category_name": "Groceries",
                "account_name": "Chase Checking",
                "cleared": "cleared",
            },
        ]
    }
}

FINAL_ANALYSIS = """\
## Grocery Spending — February 2026

| Date | Payee | Amount |
|------|-------|--------|
| Feb 15 | Whole Foods | $52.34 |
| Feb 20 | Trader Joe's | $31.20 |
| Feb 22 | Costco | $15.80 |

**Total: $99.34**

You've spent $99.34 on groceries this month across 3 transactions. \
Whole Foods is your largest grocery expense at $52.34. \
All transactions are cleared in your Chase Checking account."""


# ---------------------------------------------------------------------------
# Helpers — build realistic ADK events
# ---------------------------------------------------------------------------


def _tool_call_event(author: str, tool_name: str, args: dict) -> Event:
    """Simulate Gemini deciding to call a YNAB tool."""
    return Event(
        author=author,
        content=types.Content(
            role="model",
            parts=[
                types.Part(
                    function_call=types.FunctionCall(name=tool_name, args=args)
                )
            ],
        ),
    )


def _tool_response_event(author: str, tool_name: str, response: dict) -> Event:
    """Simulate the YNAB API returning data."""
    return Event(
        author=author,
        content=types.Content(
            role="tool",
            parts=[
                types.Part(
                    function_response=types.FunctionResponse(
                        name=tool_name, response=response
                    )
                )
            ],
        ),
    )


def _text_event(author: str, text: str) -> Event:
    """Simulate Gemini producing a final text response."""
    return Event(
        author=author,
        content=types.Content(
            role="model",
            parts=[types.Part(text=text)],
        ),
    )


# ---------------------------------------------------------------------------
# E2E tests — full PyFlow pipeline, mocked at Runner.run_async
# ---------------------------------------------------------------------------


class TestBudgetAnalystE2E:
    """Simulate real user interactions with the budget_analyst agent.

    Each test boots the real platform, calls platform.run_workflow() with a
    natural language message, and verifies the response. The ADK Runner's
    run_async is mocked to return a realistic sequence of events that mirrors
    what Gemini + YNAB would produce in production.
    """

    async def test_ask_grocery_spending(self):
        """User asks: 'How much did I spend on groceries this month?'

        Expected flow:
        1. Agent calls getBudgets → discovers 'My Household Budget'
        2. Agent calls getTransactionsByAccount with since_date → gets 3 txns
        3. Agent responds with formatted spending summary
        """
        config = PlatformConfig(workflows_dir="agents", load_dotenv=False)
        platform = PyFlowPlatform(config)
        await platform.boot()

        events = [
            # Step 1: Gemini calls getBudgets
            _tool_call_event("analyst", "getBudgets", {}),
            _tool_response_event("analyst", "getBudgets", YNAB_BUDGETS_RESPONSE),
            # Step 2: Gemini calls getTransactionsByAccount with since_date
            _tool_call_event(
                "analyst",
                "getTransactionsByAccount",
                {
                    "budget_id": "budget-001",
                    "account_id": "all",
                    "since_date": "2026-02-01",
                    "type": "uncategorized",
                },
            ),
            _tool_response_event(
                "analyst", "getTransactionsByAccount", YNAB_TRANSACTIONS_RESPONSE
            ),
            # Step 3: Gemini generates the final analysis
            _text_event("analyst", FINAL_ANALYSIS),
        ]

        async def mock_run_async(self_runner, **kwargs):
            for event in events:
                yield event

        with patch.object(Runner, "run_async", mock_run_async):
            result = await platform.run_workflow(
                "budget_analyst",
                {"message": "How much did I spend on groceries this month?"},
            )

        # Verify the response
        assert result.content == FINAL_ANALYSIS
        assert result.author == "analyst"
        assert result.session_id is not None
        await platform.shutdown()

    async def test_ask_with_custom_user_id(self):
        """User sends a request with a specific user_id."""
        config = PlatformConfig(workflows_dir="agents", load_dotenv=False)
        platform = PyFlowPlatform(config)
        await platform.boot()

        events = [
            _tool_call_event("analyst", "getBudgets", {}),
            _tool_response_event("analyst", "getBudgets", YNAB_BUDGETS_RESPONSE),
            _text_event("analyst", "You have 1 budget: My Household Budget."),
        ]

        async def mock_run_async(self_runner, **kwargs):
            # Verify user_id is passed through
            assert kwargs.get("user_id") == "user-42"
            for event in events:
                yield event

        with patch.object(Runner, "run_async", mock_run_async):
            result = await platform.run_workflow(
                "budget_analyst",
                {"message": "List my budgets"},
                user_id="user-42",
            )

        assert "My Household Budget" in result.content
        await platform.shutdown()

    async def test_session_has_datetime_state(self):
        """The session is created with current date/time injected into state."""
        config = PlatformConfig(workflows_dir="agents", load_dotenv=False)
        platform = PyFlowPlatform(config)
        await platform.boot()

        captured_session_id = None

        async def mock_run_async(self_runner, **kwargs):
            nonlocal captured_session_id
            captured_session_id = kwargs.get("session_id")
            # Verify session was created by checking we got a session_id
            assert captured_session_id is not None

            # Verify session state has datetime vars
            session = await self_runner.session_service.get_session(
                app_name="pyflow",
                user_id=kwargs["user_id"],
                session_id=captured_session_id,
            )
            assert "current_date" in session.state
            assert "current_datetime" in session.state
            assert "timezone" in session.state
            assert session.state["current_date"].startswith("2026-")

            yield _text_event("analyst", "Today is a good day for budgeting.")

        with patch.object(Runner, "run_async", mock_run_async):
            result = await platform.run_workflow(
                "budget_analyst",
                {"message": "What's the date?"},
            )

        assert result.content == "Today is a good day for budgeting."
        assert result.session_id == captured_session_id
        await platform.shutdown()

    async def test_empty_response_from_agent(self):
        """If the agent produces no final response, result.content is empty."""
        config = PlatformConfig(workflows_dir="agents", load_dotenv=False)
        platform = PyFlowPlatform(config)
        await platform.boot()

        # Only tool call events, no final text
        events = [
            _tool_call_event("analyst", "getBudgets", {}),
            _tool_response_event("analyst", "getBudgets", YNAB_BUDGETS_RESPONSE),
        ]

        async def mock_run_async(self_runner, **kwargs):
            for event in events:
                yield event

        with patch.object(Runner, "run_async", mock_run_async):
            result = await platform.run_workflow(
                "budget_analyst",
                {"message": "Hello"},
            )

        assert result.content == ""
        await platform.shutdown()

    async def test_multi_step_spending_analysis(self):
        """Simulate a complex multi-step interaction: plan → budgets → categories → analysis.

        This mirrors PlanReAct behavior where the agent plans before executing.
        """
        config = PlatformConfig(workflows_dir="agents", load_dotenv=False)
        platform = PyFlowPlatform(config)
        await platform.boot()

        categories_response = {
            "data": {
                "category_groups": [
                    {
                        "name": "Everyday Expenses",
                        "categories": [
                            {
                                "name": "Groceries",
                                "budgeted": 400000,
                                "activity": -99340,
                                "balance": 300660,
                            },
                            {
                                "name": "Restaurants",
                                "budgeted": 200000,
                                "activity": -145600,
                                "balance": 54400,
                            },
                        ],
                    }
                ]
            }
        }

        analysis = (
            "## Budget Overview — February 2026\n\n"
            "**Groceries**: Spent $99.34 of $400.00 budget (24.8%) — $300.66 remaining\n"
            "**Restaurants**: Spent $145.60 of $200.00 budget (72.8%) — $54.40 remaining\n\n"
            "Watch out: restaurant spending is at 73% of budget with a week left in the month."
        )

        events = [
            # Plan step (PlanReAct often produces a plan first)
            _text_event("analyst", ""),  # empty plan acknowledgment
            # Step 1: Get budgets
            _tool_call_event("analyst", "getBudgets", {}),
            _tool_response_event("analyst", "getBudgets", YNAB_BUDGETS_RESPONSE),
            # Step 2: Get categories for the budget
            _tool_call_event(
                "analyst",
                "getBudgetById",
                {"budget_id": "budget-001"},
            ),
            _tool_response_event("analyst", "getBudgetById", categories_response),
            # Step 3: Final analysis
            _text_event("analyst", analysis),
        ]

        async def mock_run_async(self_runner, **kwargs):
            for event in events:
                yield event

        with patch.object(Runner, "run_async", mock_run_async):
            result = await platform.run_workflow(
                "budget_analyst",
                {"message": "Give me an overview of my budget this month"},
            )

        assert "Groceries" in result.content
        assert "Restaurants" in result.content
        assert "$99.34" in result.content
        assert "73%" in result.content
        await platform.shutdown()


# ---------------------------------------------------------------------------
# Workflow YAML validation (fast, no boot)
# ---------------------------------------------------------------------------


class TestBudgetAnalystYaml:
    """Validate workflow.yaml structure and constraints."""

    def test_openapi_tools_from_project_config(self):
        """openapi_tools is defined in pyflow.yaml (infrastructure), filtering in workflow YAML."""
        import yaml

        from pyflow.models.project import ProjectConfig
        from pyflow.models.workflow import WorkflowDef

        # pyflow.yaml at project root defines the tool (no tool_filter)
        config = ProjectConfig.from_yaml(Path("pyflow.yaml"))
        assert "ynab" in config.openapi_tools
        assert config.openapi_tools["ynab"].spec == "specs/ynab-v1-openapi.yaml"
        assert config.openapi_tools["ynab"].auth.type == "bearer"
        assert config.openapi_tools["ynab"].auth.token_env == "PYFLOW_YNAB_API_TOKEN"

        # workflow.yaml has no openapi_tools section
        wf_path = Path("agents/budget_analyst/workflow.yaml")
        raw = yaml.safe_load(wf_path.read_text())
        assert "openapi_tools" not in raw

        # Agent references ynab by name (full toolset, no filter)
        wf = WorkflowDef.from_yaml(wf_path)
        assert "ynab" in wf.agents[0].tools

    def test_agent_config(self):
        from pyflow.models.workflow import WorkflowDef

        wf = WorkflowDef.from_yaml(Path("agents/budget_analyst/workflow.yaml"))
        agent = wf.agents[0]
        assert agent.name == "analyst"
        assert agent.model == "gemini-2.5-flash"
        assert agent.temperature == 0.2
        assert agent.max_output_tokens == 4096
        assert agent.tools == ["ynab"]
        assert agent.output_key == "analysis"
        assert "milliunits" in (agent.instruction or "")

    def test_spec_file_valid(self):
        import yaml

        spec = yaml.safe_load(Path("specs/ynab-v1-openapi.yaml").read_text())
        assert spec["openapi"].startswith("3.")
        assert "/user" in spec["paths"]
        assert "https://api.ynab.com/v1" in spec["servers"][0]["url"]


# ---------------------------------------------------------------------------
# Hydration validation (real boot, no run)
# ---------------------------------------------------------------------------


class TestBudgetAnalystHydration:
    """Verify the hydrated agent tree matches expectations."""

    async def test_hydrated_agent_has_openapi_toolset(self):
        from google.adk.agents.llm_agent import LlmAgent
        from google.adk.planners.plan_re_act_planner import PlanReActPlanner
        from google.adk.tools.openapi_tool.openapi_spec_parser.openapi_toolset import (
            OpenAPIToolset,
        )

        config = PlatformConfig(workflows_dir="agents", load_dotenv=False)
        platform = PyFlowPlatform(config)
        await platform.boot()

        agent = platform.workflows.get("budget_analyst").agent
        assert isinstance(agent, LlmAgent)
        assert isinstance(agent.planner, PlanReActPlanner)
        assert len(agent.tools) == 1
        assert isinstance(agent.tools[0], OpenAPIToolset)
        assert "ynab" in platform.tools
        await platform.shutdown()
