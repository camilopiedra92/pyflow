from __future__ import annotations

from typing import Callable

from google.adk.plugins import LoggingPlugin

_PLUGIN_FACTORIES: dict[str, Callable] = {
    "logging": lambda: LoggingPlugin(),
}

# ReflectAndRetryToolPlugin is experimental, import conditionally
try:
    from google.adk.plugins import ReflectAndRetryToolPlugin

    _PLUGIN_FACTORIES["reflect_and_retry"] = lambda: ReflectAndRetryToolPlugin()
except ImportError:
    pass


def resolve_plugins(names: list[str]) -> list:
    """Resolve plugin names to ADK plugin instances. Unknown names are skipped."""
    return [_PLUGIN_FACTORIES[name]() for name in names if name in _PLUGIN_FACTORIES]
