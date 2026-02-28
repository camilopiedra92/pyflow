from __future__ import annotations

import pytest
from pydantic import ValidationError

from pyflow.models.platform import PlatformConfig


class TestPlatformConfig:
    def test_defaults(self):
        config = PlatformConfig()
        assert config.tools_dir == "pyflow/tools"
        assert config.workflows_dir == "workflows"
        assert config.log_level == "INFO"
        assert config.host == "0.0.0.0"
        assert config.port == 8000

    def test_overrides(self):
        config = PlatformConfig(
            tools_dir="custom/tools",
            workflows_dir="custom/workflows",
            log_level="DEBUG",
            host="127.0.0.1",
            port=9000,
        )
        assert config.tools_dir == "custom/tools"
        assert config.workflows_dir == "custom/workflows"
        assert config.log_level == "DEBUG"
        assert config.host == "127.0.0.1"
        assert config.port == 9000

    def test_port_min_bound(self):
        with pytest.raises(ValidationError):
            PlatformConfig(port=0)

    def test_port_max_bound(self):
        with pytest.raises(ValidationError):
            PlatformConfig(port=70000)

    def test_invalid_log_level(self):
        with pytest.raises(ValidationError):
            PlatformConfig(log_level="TRACE")
