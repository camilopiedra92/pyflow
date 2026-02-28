# Budget Analyst Workflow Design

## Overview

Agentic YNAB workflow: a single ReAct LLM agent with `plan_react` planner that answers natural language questions about the user's budget by autonomously calling YNAB API actions.

## Architecture

- **Orchestration:** `react` with `plan_react` planner
- **Agent:** Single `llm` agent (`analyst`) with `ynab` tool
- **Model:** `gemini-2.5-flash`

The planner generates a structured plan of YNAB API calls, then executes them step-by-step. It can re-plan if it discovers new information mid-execution.

## Agent Behavior

1. Receives `{current_date}` and `{timezone}` from platform session state
2. Always starts with `list_budgets` to discover the budget ID
3. Plans which subsequent API calls are needed to answer the question
4. ALWAYS uses `since_date` when fetching transactions (unfiltered = 167KB, filtered = 26KB)
5. Executes calls, gathering data across accounts, categories, transactions, etc.
6. Converts YNAB milliunits (1000 = $1.00) to human-readable currency
7. Synthesizes a clear, formatted answer

## Available YNAB Actions

| Category | Actions |
|----------|---------|
| Budgets | `list_budgets`, `get_budget` |
| Accounts | `list_accounts`, `get_account` |
| Categories | `list_categories`, `get_category` |
| Transactions | `list_transactions`, `get_transaction`, `create_transaction` |
| Scheduled | `list_scheduled_transactions` |
| Months | `list_months`, `get_month_category` |

## Example Queries

- "How much did I spend on groceries this month?"
- "What are my account balances?"
- "Show me my top spending categories"
- "What upcoming scheduled transactions do I have?"
- "Am I over budget in any category?"

## A2A

Exposes `budget_analysis` skill tagged with `finance`, `budget`, `ynab`.

## Lessons Learned

- **Always filter transactions:** Unfiltered `list_transactions` returns 167KB (232 txns) vs 26KB filtered by month. Without `since_date`, the LLM context explodes and hits Gemini's 1M token/min rate limit.
- **LLMs don't know the date:** The platform now injects `{current_date}` into session state. Without this, the agent guessed wrong dates.
- **PlanReAct > vanilla ReAct for data-heavy APIs:** PlanReAct plans filters upfront (~52K tokens). Vanilla ReAct fetches everything first (~167K tokens).

## Implementation

Single file: `workflows/budget_analyst.yaml`
No new code needed — uses existing `ynab` tool and `react` orchestration with `plan_react` planner.
