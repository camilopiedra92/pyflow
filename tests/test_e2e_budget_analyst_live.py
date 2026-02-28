"""Live end-to-end test for the budget_analyst agent.

Calls the real Gemini LLM and real YNAB API — requires API keys.
Skipped automatically when GOOGLE_API_KEY or PYFLOW_YNAB_API_TOKEN are not set.

Run manually:
    pytest tests/test_e2e_budget_analyst_live.py -v -s
"""

from __future__ import annotations

import os

import pytest
from dotenv import dotenv_values

from pyflow.models.platform import PlatformConfig
from pyflow.platform.app import PyFlowPlatform

# Check keys without polluting os.environ (platform.boot() loads .env itself)
_dotenv = dotenv_values()
_has_keys = bool(os.environ.get("GOOGLE_API_KEY") or _dotenv.get("GOOGLE_API_KEY")) and bool(
    os.environ.get("PYFLOW_YNAB_API_TOKEN") or _dotenv.get("PYFLOW_YNAB_API_TOKEN")
)
skip_reason = "Requires GOOGLE_API_KEY and PYFLOW_YNAB_API_TOKEN"


@pytest.fixture
async def platform():
    """Boot a real platform with .env loaded."""
    config = PlatformConfig(workflows_dir="agents")
    p = PyFlowPlatform(config)
    await p.boot()
    yield p
    await p.shutdown()


@pytest.mark.skipif(not _has_keys, reason=skip_reason)
class TestBudgetAnalystLive:
    """Live tests against Gemini + YNAB.

    Each test sends a real message through the full pipeline:
    PyFlowPlatform.boot() → run_workflow() → Gemini LLM → YNAB API → response.
    """

    async def test_list_budgets(self, platform: PyFlowPlatform):
        """Ask the agent to list all budgets."""
        result = await platform.run_workflow(
            "budget_analyst",
            {
                "message": (
                    "Muéstrame todos mis presupuestos. "
                    "Solo el nombre y moneda de cada uno. "
                    "Usa get_plans para obtener la lista."
                )
            },
        )

        assert result.content, "Agent returned empty response"
        assert result.session_id
        assert result.usage
        assert result.usage.tool_calls >= 1
        assert result.usage.total_tokens > 0

    async def test_overspending_categories(self, platform: PyFlowPlatform):
        """Ask about overspending categories in the shared budget.

        Full real flow:
        1. Gemini calls get_plans → finds "Compartido - COP" budget
        2. Gemini calls get_plan_month for Feb 2026 → gets category balances
        3. Gemini filters negative balances and formats as table
        """
        result = await platform.run_workflow(
            "budget_analyst",
            {
                "message": (
                    'En el presupuesto "Compartido - COP", qué categorías tienen '
                    "overspending en febrero 2026? Muestra nombre de categoría, "
                    "presupuestado, actividad y balance. "
                    "Usa get_plan_month con el mes 2026-02-01."
                )
            },
        )

        assert result.content, "Agent returned empty response"
        assert result.author == "analyst"
        assert result.session_id

        # The agent should identify overspending categories with amounts
        content = result.content
        assert "$" in content or "presupuest" in content.lower()

        # Usage: at least get_plans + get_plan_month
        assert result.usage
        assert result.usage.tool_calls >= 2
        assert result.usage.llm_calls >= 2
