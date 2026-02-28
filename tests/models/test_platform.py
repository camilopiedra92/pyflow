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


class TestPlatformConfigSecrets:
    def test_secrets_default_empty(self):
        config = PlatformConfig()
        assert config.secrets == {}

    def test_secrets_accepts_dict(self):
        config = PlatformConfig(secrets={"ynab_api_token": "abc123"})
        assert config.secrets["ynab_api_token"] == "abc123"

    def test_secrets_multiple_keys(self):
        config = PlatformConfig(secrets={"key1": "val1", "key2": "val2"})
        assert len(config.secrets) == 2
