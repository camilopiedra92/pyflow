from __future__ import annotations

import os
from unittest.mock import patch, MagicMock

from typer.testing import CliRunner

from pyflow.cli import app

runner = CliRunner()


class TestServeCommand:
    def test_serve_sets_env_vars(self):
        """serve command propagates host/port/workflows-dir via env vars."""
        with patch("uvicorn.run") as mock_run:
            result = runner.invoke(
                app,
                ["serve", "--host", "127.0.0.1", "--port", "9000", "--workflows-dir", "custom"],
            )
            assert result.exit_code == 0
            mock_run.assert_called_once_with(
                "pyflow.server:app", host="127.0.0.1", port=9000, reload=False
            )

    def test_serve_defaults(self):
        """serve command uses default host/port when no flags given."""
        with patch("uvicorn.run") as mock_run:
            result = runner.invoke(app, ["serve"])
            assert result.exit_code == 0
            mock_run.assert_called_once_with(
                "pyflow.server:app", host="0.0.0.0", port=8000, reload=False
            )

    def test_serve_propagates_workflows_dir(self):
        """serve command sets PYFLOW_WORKFLOWS_DIR env var."""
        captured_env = {}

        def capture_run(*args, **kwargs):
            captured_env["PYFLOW_WORKFLOWS_DIR"] = os.environ.get("PYFLOW_WORKFLOWS_DIR")
            captured_env["PYFLOW_HOST"] = os.environ.get("PYFLOW_HOST")
            captured_env["PYFLOW_PORT"] = os.environ.get("PYFLOW_PORT")

        with patch("uvicorn.run", side_effect=capture_run):
            result = runner.invoke(
                app,
                ["serve", "--host", "10.0.0.1", "--port", "3000", "--workflows-dir", "my_agents"],
            )
            assert result.exit_code == 0
            assert captured_env["PYFLOW_WORKFLOWS_DIR"] == "my_agents"
            assert captured_env["PYFLOW_HOST"] == "10.0.0.1"
            assert captured_env["PYFLOW_PORT"] == "3000"
