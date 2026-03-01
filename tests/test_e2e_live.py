"""Live end-to-end tests for exchange_tracker and budget_analyst workflows.

Calls the real Gemini LLM and real external APIs (open.er-api.com, YNAB).
Skipped automatically when required API keys are not set.

Run manually:
    pytest tests/test_e2e_live.py -v -s
"""

from __future__ import annotations

import os

import pytest
from dotenv import dotenv_values

from pyflow.models.platform import PlatformConfig
from pyflow.platform.app import PyFlowPlatform

# ---------------------------------------------------------------------------
# Key detection (without polluting os.environ — platform.boot() loads .env)
# ---------------------------------------------------------------------------

_dotenv = dotenv_values()

_has_google = bool(
    os.environ.get("GOOGLE_API_KEY") or _dotenv.get("GOOGLE_API_KEY")
)
_has_ynab = bool(
    os.environ.get("PYFLOW_YNAB_API_TOKEN") or _dotenv.get("PYFLOW_YNAB_API_TOKEN")
)


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------


@pytest.fixture
async def platform():
    """Boot a real platform with .env loaded."""
    config = PlatformConfig(workflows_dir="agents")
    p = PyFlowPlatform(config)
    await p.boot()
    yield p
    await p.shutdown()


# ---------------------------------------------------------------------------
# exchange_tracker — live tests (Gemini + open.er-api.com)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _has_google, reason="Requires GOOGLE_API_KEY")
class TestExchangeTrackerLive:
    """Live tests against Gemini + open.er-api.com.

    Each test sends a real message through the full 7-step pipeline:
    LLM parser → CodeAgent → ExprAgent (build_url) → ToolAgent (http_request)
    → ExprAgent (extract_rate) → ExprAgent (check_threshold) → LLM reporter.
    """

    async def test_usd_to_eur_rate(self, platform: PyFlowPlatform):
        """Ask for a simple USD to EUR exchange rate."""
        result = await platform.run_workflow(
            "exchange_tracker",
            {"message": "What is the current USD to EUR exchange rate?"},
        )

        assert result.content, "Agent returned empty response"
        assert result.session_id
        assert result.usage
        assert result.usage.llm_calls >= 2  # parser + reporter
        assert result.usage.total_tokens > 0

        # The response should mention currency info
        content = result.content.lower()
        assert "usd" in content or "eur" in content or "rate" in content

    async def test_gbp_to_jpy_with_threshold(self, platform: PyFlowPlatform):
        """Ask about GBP to JPY with a threshold — tests all 7 pipeline steps."""
        result = await platform.run_workflow(
            "exchange_tracker",
            {"message": "Is the GBP to JPY rate above 190?"},
        )

        assert result.content, "Agent returned empty response"
        assert result.session_id
        assert result.usage
        assert result.usage.llm_calls >= 2  # parser + reporter

        # The response should discuss the rate and the threshold
        content = result.content.lower()
        assert any(
            word in content for word in ["gbp", "jpy", "rate", "threshold", "190", "above", "below"]
        )

    async def test_cop_to_usd_rate(self, platform: PyFlowPlatform):
        """Ask for a less common currency pair — COP to USD."""
        result = await platform.run_workflow(
            "exchange_tracker",
            {"message": "Cuánto vale el peso colombiano contra el dólar? COP to USD"},
        )

        assert result.content, "Agent returned empty response"
        assert result.session_id


# ---------------------------------------------------------------------------
# budget_analyst — live tests (Gemini + YNAB API)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not (_has_google and _has_ynab),
    reason="Requires GOOGLE_API_KEY and PYFLOW_YNAB_API_TOKEN",
)
class TestBudgetAnalystLive:
    """Live tests against Gemini + YNAB API.

    Each test sends a real message through the full ReAct pipeline:
    PyFlowPlatform.boot() → run_workflow() → Gemini (PlanReAct) → YNAB API → response.
    """

    async def test_list_budgets(self, platform: PyFlowPlatform):
        """Ask the agent to list all budgets — simplest possible query."""
        result = await platform.run_workflow(
            "budget_analyst",
            {"message": "List all my budgets with their names and currencies."},
        )

        assert result.content, "Agent returned empty response"
        assert result.session_id
        assert result.usage
        assert result.usage.tool_calls >= 1  # at least getBudgets
        assert result.usage.total_tokens > 0

    async def test_category_overview(self, platform: PyFlowPlatform):
        """Ask for a budget category overview — exercises multi-step tool use.

        Flow: Gemini plans → getBudgets → getBudgetById or getCategories → analysis.
        """
        result = await platform.run_workflow(
            "budget_analyst",
            {
                "message": (
                    "Show me the budget categories and their balances "
                    "for the current month. Use the first budget you find."
                )
            },
        )

        assert result.content, "Agent returned empty response"
        assert result.author == "analyst"
        assert result.session_id
        assert result.usage
        assert result.usage.tool_calls >= 2  # getBudgets + getCategories/getBudgetMonth
        assert result.usage.llm_calls >= 2
