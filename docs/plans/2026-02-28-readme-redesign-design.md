# README Redesign — Design Document

**Date**: 2026-02-28
**Goal**: Transform the README into a professional portfolio-quality showcase with full technical depth.
**Audience**: Developers evaluating the project as portfolio work — first impression matters.
**Approach**: Visual-First Showcase — everything in the README, no external docs links.

---

## Design Decisions

1. **All content in README** — for portfolio, the README IS the project. Nobody clicks through to docs/.
2. **Real example, not simplified** — show the exchange_tracker 7-step pipeline (4 agent types in one workflow).
3. **Fix stale data** — update test count (482), remove agent-card.json references, fix tool counts.
4. **Badges** — Python version, License, Test count, Google ADK. Using shields.io static badges.
5. **Structured features** — grouped by category instead of flat list.
6. **Agent types table** — all 7 types (llm, code, tool, expr, sequential, parallel, loop) with descriptions.
7. **Updated architecture tree** — reflects current state (no agent-card.json, includes schema.py, expr_agent.py).
8. **CLI reference table** — all commands in a clean table format.

---

## Section Structure (12 sections)

### 1. Hero + Badges
- Project name, one-line tagline, shields.io badges
- 3-line description paragraph

### 2. Features
- Grouped: Core, Multi-Model, Security, Protocol, Developer Experience
- Each group has 2-4 bullet points

### 3. Quickstart
- venv setup, install, run, serve, validate, list, init
- Clean code block

### 4. Example Workflow
- Full exchange_tracker workflow (7 agents, 4 types)
- Brief annotation explaining each step

### 5. Agent Types
- Table with all 7 types: llm, code, tool, expr, sequential, parallel, loop
- Each with purpose and key fields

### 6. Multi-Model Support
- YAML example with Gemini, Anthropic, OpenAI
- LiteLLM install note

### 7. Platform Tools
- Table: 6 custom tools + 9 ADK built-in tools (separate table)
- Each with name, description

### 8. Architecture
- Updated file tree (no agent-card.json, includes expr_agent.py, schema.py, etc.)
- Boot sequence diagram

### 9. A2A Protocol
- Explanation of auto-generated cards
- API endpoints table

### 10. CLI Reference
- Table with all pyflow commands

### 11. Development
- Setup, run tests, lint

### 12. Tech Stack + License
- Tech stack with links
- MIT license

---

## Stale Content to Fix

| Issue | Current | Correct |
|-------|---------|---------|
| Test count | "430 Tests" | "482 Tests" |
| Architecture tree | Shows `agent-card.json` | Remove (cards are generated, not static) |
| Architecture tree | Missing `schema.py`, `expr_agent.py` | Add them |
| A2A cards description | "Load static agent-card.json" | "Generate cards from workflow definitions" |
| Tool count | "6 Built-in Tools" | "6 Platform Tools + 9 ADK Built-in Tools" |
| pyproject.toml description | "Config-driven workflow automation engine" | Keep as-is (separate concern) |
