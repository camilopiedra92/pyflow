from __future__ import annotations

from typing import Callable

from google.adk.plugins import DebugLoggingPlugin, LoggingPlugin, ReflectAndRetryToolPlugin
from google.adk.plugins.context_filter_plugin import ContextFilterPlugin
from google.adk.plugins.multimodal_tool_results_plugin import MultimodalToolResultsPlugin
from google.adk.plugins.save_files_as_artifacts_plugin import SaveFilesAsArtifactsPlugin

_PLUGIN_FACTORIES: dict[str, Callable] = {
    "logging": lambda: LoggingPlugin(),
    "debug_logging": lambda: DebugLoggingPlugin(),
    "reflect_and_retry": lambda: ReflectAndRetryToolPlugin(),
    "context_filter": lambda: ContextFilterPlugin(),
    "save_files_as_artifacts": lambda: SaveFilesAsArtifactsPlugin(),
    "multimodal_tool_results": lambda: MultimodalToolResultsPlugin(),
}


def resolve_plugins(names: list[str]) -> list:
    """Resolve plugin names to ADK plugin instances. Unknown names are skipped."""
    return [_PLUGIN_FACTORIES[name]() for name in names if name in _PLUGIN_FACTORIES]
