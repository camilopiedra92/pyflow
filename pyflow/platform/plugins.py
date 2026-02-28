from __future__ import annotations

import os
from typing import Callable

from google.adk.plugins import DebugLoggingPlugin, LoggingPlugin, ReflectAndRetryToolPlugin
from google.adk.plugins.context_filter_plugin import ContextFilterPlugin
from google.adk.plugins.multimodal_tool_results_plugin import MultimodalToolResultsPlugin
from google.adk.plugins.save_files_as_artifacts_plugin import SaveFilesAsArtifactsPlugin


def _bigquery_analytics_factory():
    """Create BigQuery analytics plugin from env vars. Returns None if not configured."""
    project_id = os.environ.get("PYFLOW_BQ_PROJECT_ID")
    dataset_id = os.environ.get("PYFLOW_BQ_DATASET_ID")
    if not project_id or not dataset_id:
        return None
    from google.adk.plugins.bigquery_agent_analytics_plugin import (
        BigQueryAgentAnalyticsPlugin,
    )
    return BigQueryAgentAnalyticsPlugin(project_id=project_id, dataset_id=dataset_id)


_PLUGIN_FACTORIES: dict[str, Callable] = {
    "logging": lambda: LoggingPlugin(),
    "debug_logging": lambda: DebugLoggingPlugin(),
    "reflect_and_retry": lambda: ReflectAndRetryToolPlugin(),
    "context_filter": lambda: ContextFilterPlugin(),
    "save_files_as_artifacts": lambda: SaveFilesAsArtifactsPlugin(),
    "multimodal_tool_results": lambda: MultimodalToolResultsPlugin(),
    "bigquery_analytics": _bigquery_analytics_factory,
}


def resolve_plugins(names: list[str]) -> list:
    """Resolve plugin names to ADK plugin instances. Unknown/unconfigured names are skipped."""
    plugins = []
    for name in names:
        if name in _PLUGIN_FACTORIES:
            plugin = _PLUGIN_FACTORIES[name]()
            if plugin is not None:
                plugins.append(plugin)
    return plugins
