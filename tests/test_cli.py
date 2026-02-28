"""Tests for the rewritten Typer CLI (ADK platform commands)."""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from pyflow.cli import app
from pyflow.models.tool import ToolMetadata
from pyflow.models.workflow import WorkflowDef

runner = CliRunner()


def _make_mock_platform(
    run_result: dict | None = None,
    tools: list[ToolMetadata] | None = None,
    workflows: list[WorkflowDef] | None = None,
):
    """Create a mock PyFlowPlatform with configurable returns."""
    mock = MagicMock()
    mock.boot = AsyncMock()
    mock.shutdown = AsyncMock()
    mock.run_workflow = AsyncMock(return_value=run_result or {"status": "ok"})
    mock.list_tools = MagicMock(return_value=tools or [])
    mock.list_workflows = MagicMock(return_value=workflows or [])
    return mock


class TestRunCommand:
    def test_run_command_success(self):
        mock_platform = _make_mock_platform(run_result={"output": "done"})
        with patch("pyflow.cli.PyFlowPlatform", return_value=mock_platform):
            result = runner.invoke(app, ["run", "my_workflow"])
        assert result.exit_code == 0
        assert '"output": "done"' in result.stdout
        mock_platform.boot.assert_awaited_once()
        mock_platform.run_workflow.assert_awaited_once_with("my_workflow", {})
        mock_platform.shutdown.assert_awaited_once()

    def test_run_invalid_json_input(self):
        result = runner.invoke(app, ["run", "my_workflow", "--input", "{bad json}"])
        assert result.exit_code == 1
        assert "Invalid JSON input" in result.output


class TestValidateCommand:
    def test_validate_valid_yaml(self):
        yaml_content = """\
name: test_workflow
description: A test workflow
agents:
  - name: agent1
    type: llm
    model: gpt-4
    instruction: Do something
    tools: []
    output_key: result
orchestration:
  type: sequential
  agents: [agent1]
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            result = runner.invoke(app, ["validate", f.name])
        assert result.exit_code == 0
        assert "Valid workflow: test_workflow" in result.stdout

    def test_validate_missing_file(self):
        result = runner.invoke(app, ["validate", "/nonexistent/path.yaml"])
        assert result.exit_code == 1
        assert "File not found" in result.output

    def test_validate_invalid_yaml(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("name: bad\n")  # Missing required fields
            f.flush()
            result = runner.invoke(app, ["validate", f.name])
        assert result.exit_code == 1
        assert "Validation error" in result.output


class TestListCommand:
    def test_list_tools(self):
        tools = [
            ToolMetadata(name="http_request", description="Make HTTP requests"),
            ToolMetadata(name="transform", description="Transform data"),
        ]
        mock_platform = _make_mock_platform(tools=tools)
        with patch("pyflow.cli.PyFlowPlatform", return_value=mock_platform):
            result = runner.invoke(app, ["list", "--tools"])
        assert result.exit_code == 0
        assert "http_request" in result.stdout
        assert "Make HTTP requests" in result.stdout
        assert "transform" in result.stdout
        mock_platform.boot.assert_awaited_once()
        mock_platform.shutdown.assert_awaited_once()

    def test_list_workflows(self):
        from pyflow.models.agent import AgentConfig
        from pyflow.models.workflow import OrchestrationConfig

        wf = WorkflowDef(
            name="my_workflow",
            description="Test workflow",
            agents=[
                AgentConfig(
                    name="a1", type="llm", model="gpt-4", instruction="Do things"
                )
            ],
            orchestration=OrchestrationConfig(type="sequential", agents=["a1"]),
        )
        mock_platform = _make_mock_platform(workflows=[wf])
        with patch("pyflow.cli.PyFlowPlatform", return_value=mock_platform):
            result = runner.invoke(app, ["list", "--workflows"])
        assert result.exit_code == 0
        assert "my_workflow" in result.stdout
        assert "Test workflow" in result.stdout
        mock_platform.boot.assert_awaited_once()
        mock_platform.shutdown.assert_awaited_once()

    def test_list_no_flag(self):
        mock_platform = _make_mock_platform()
        with patch("pyflow.cli.PyFlowPlatform", return_value=mock_platform):
            result = runner.invoke(app, ["list"])
        assert result.exit_code == 0
        assert "--tools" in result.stdout or "--workflows" in result.stdout
