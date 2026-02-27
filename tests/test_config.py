from __future__ import annotations

import structlog
from pyflow.config import configure_logging


class TestConfigureLogging:
    def test_console_renderer(self):
        configure_logging(json_output=False)
        config = structlog.get_config()
        processor_types = [type(p) for p in config["processors"]]
        assert structlog.dev.ConsoleRenderer in processor_types

    def test_json_renderer(self):
        configure_logging(json_output=True)
        config = structlog.get_config()
        processor_types = [type(p) for p in config["processors"]]
        assert structlog.processors.JSONRenderer in processor_types

    def test_custom_level(self):
        configure_logging(level=10)
        config = structlog.get_config()
        # wrapper_class is a filtering bound logger with the given level
        assert config["wrapper_class"] is not None
