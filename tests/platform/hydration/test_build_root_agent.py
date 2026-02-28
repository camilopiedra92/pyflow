"""Tests for the build_root_agent factory function."""
from __future__ import annotations

from pathlib import Path

import pytest

from pyflow.platform.hydration.hydrator import build_root_agent


class TestBuildRootAgent:
    def test_builds_agent_from_workflow_yaml(self, tmp_path: Path) -> None:
        """build_root_agent() hydrates workflow.yaml next to the caller file."""
        yaml_content = """\
name: test_factory
description: "Factory test workflow"
agents:
  - name: main
    type: llm
    model: gemini-2.5-flash
    instruction: "You are helpful."
    output_key: result
orchestration:
  type: sequential
  agents: [main]
"""
        (tmp_path / "workflow.yaml").write_text(yaml_content)
        fake_caller = tmp_path / "agent.py"
        fake_caller.touch()

        agent = build_root_agent(str(fake_caller))

        assert agent.name == "test_factory"

    def test_raises_on_missing_yaml(self, tmp_path: Path) -> None:
        """build_root_agent() raises if workflow.yaml is missing."""
        fake_caller = tmp_path / "agent.py"
        fake_caller.touch()

        with pytest.raises(FileNotFoundError):
            build_root_agent(str(fake_caller))
