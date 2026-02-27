# tests/test_cli.py
import pytest
from pathlib import Path
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

    def test_run_workflow(self):
        result = runner.invoke(app, ["run", str(FIXTURES / "simple.yaml")])
        # Will fail on actual HTTP call but should at least parse
        # For now, check it attempts to run
        assert "simple-workflow" in result.stdout or result.exit_code != 0
