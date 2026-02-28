# Agent Evaluation

PyFlow agent packages are compatible with ADK's evaluation framework out of the box.

## Using `adk eval`

Each agent package exports `root_agent` via `__init__.py`, making it compatible with `adk eval`.

### Create test cases

Create a `.test.json` file in your agent package:

```json
[
  {
    "name": "basic_query",
    "input": "What is the exchange rate for USD to COP?",
    "expected_tool_use": ["http_request"],
    "expected_output_keywords": ["exchange", "rate"]
  }
]
```

### Run evaluation

```bash
adk eval agents/exchange_tracker/
```

### Evaluation types

- **Trajectory evaluation**: Verifies the agent uses the expected tools in the expected order
- **Response evaluation**: Checks final answer quality (keyword matching, LLM-as-judge)
- **Safety evaluation**: Runs safety checks on agent outputs

## Future: `pyflow eval`

A future `pyflow eval` command will wrap `adk eval` with PyFlow-specific features like workflow-level evaluation and multi-agent pipeline testing.
