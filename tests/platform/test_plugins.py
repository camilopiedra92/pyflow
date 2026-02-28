from __future__ import annotations

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
