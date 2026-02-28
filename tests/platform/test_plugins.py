from __future__ import annotations

import pytest

from pyflow.platform.plugins import resolve_plugins


class TestPluginRegistry:
    def test_resolve_logging(self):
        plugins = resolve_plugins(["logging"])
        assert len(plugins) == 1

    def test_resolve_empty_list(self):
        assert resolve_plugins([]) == []

    def test_unknown_plugin_skipped(self):
        assert resolve_plugins(["nonexistent"]) == []

    def test_resolve_multiple_with_unknown(self):
        plugins = resolve_plugins(["logging", "nonexistent"])
        assert len(plugins) == 1

    @pytest.mark.parametrize(
        "plugin_name",
        [
            "logging",
            "debug_logging",
            "reflect_and_retry",
            "context_filter",
            "save_files_as_artifacts",
            "multimodal_tool_results",
        ],
    )
    def test_resolve_each_plugin(self, plugin_name):
        """Each registered ADK plugin resolves to an instance."""
        plugins = resolve_plugins([plugin_name])
        assert len(plugins) == 1

    def test_resolve_all_plugins(self):
        """All registered plugins resolve when requested together."""
        all_names = [
            "logging",
            "debug_logging",
            "reflect_and_retry",
            "context_filter",
            "save_files_as_artifacts",
            "multimodal_tool_results",
        ]
        plugins = resolve_plugins(all_names)
        assert len(plugins) == len(all_names)
