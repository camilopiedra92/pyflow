# tests/test_cli.py
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner
from pyflow.cli import app

runner = CliRunner()
FIXTURES = Path(__file__).parent / "fixtures"


class TestCli:
    def test_validate_valid_workflow(self):
        result = runner.invoke(app, ["validate", str(FIXTURES / "simple.yaml")])
        assert result.exit_code == 0
        assert "valid" in result.stdout.lower()

    def test_validate_nonexistent(self):
        result = runner.invoke(app, ["validate", "/nonexistent.yaml"])
        assert result.exit_code != 0

    def test_list_workflows(self):
        result = runner.invoke(app, ["list", str(FIXTURES)])
        assert result.exit_code == 0
        assert "simple-workflow" in result.stdout

    def test_list_empty_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = runner.invoke(app, ["list", tmpdir])
        assert result.exit_code == 0
        assert "No workflows found" in result.stdout

    def test_run_workflow_non_network(self):
        """Run multi_step.yaml which uses condition+transform (no HTTP calls)."""
        result = runner.invoke(app, ["run", str(FIXTURES / "multi_step.yaml")])
        assert result.exit_code == 0
        assert "multi-step-test" in result.stdout
        assert "Completed" in result.stdout
        assert "start: OK" in result.stdout

    def test_run_workflow_error_handling(self):
        """Run a workflow that does not exist to test error path."""
        result = runner.invoke(app, ["run", str(FIXTURES / "nonexistent.yaml")])
        assert result.exit_code != 0

    def test_serve_command(self):
        """Test serve command mocking uvicorn.run to avoid actually starting server."""
        with patch("uvicorn.run") as mock_run:
            result = runner.invoke(
                app, ["serve", str(FIXTURES), "--host", "0.0.0.0", "--port", "9000"]
            )
        assert result.exit_code == 0
        assert "Starting PyFlow server" in result.stdout
        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args
        assert call_kwargs.kwargs["host"] == "0.0.0.0"
        assert call_kwargs.kwargs["port"] == 9000
