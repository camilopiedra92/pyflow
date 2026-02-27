from __future__ import annotations

import pytest
from pydantic import ValidationError

from pyflow.nodes.schemas import (
    AlertConfig,
    ConditionConfig,
    HttpConfig,
    StorageConfig,
    TransformConfig,
)


class TestHttpConfigValidation:
    def test_http_config_validates_url_required(self):
        with pytest.raises(ValidationError):
            HttpConfig()

    def test_http_config_default_method_is_get(self):
        cfg = HttpConfig(url="https://example.com")
        assert cfg.method == "GET"

    def test_http_config_rejects_invalid_timeout(self):
        with pytest.raises(ValidationError):
            HttpConfig(url="https://example.com", timeout=-1)
        with pytest.raises(ValidationError):
            HttpConfig(url="https://example.com", timeout=301)


class TestTransformConfigValidation:
    def test_transform_config_requires_expression(self):
        with pytest.raises(ValidationError):
            TransformConfig(input={"key": "value"})


class TestConditionConfigValidation:
    def test_condition_config_alias_if(self):
        cfg = ConditionConfig(**{"if": "True"})
        assert cfg.if_ == "True"


class TestAlertConfigValidation:
    def test_alert_config_requires_webhook_url(self):
        with pytest.raises(ValidationError):
            AlertConfig(message="hello")


class TestStorageConfigValidation:
    def test_storage_config_default_action_is_read(self):
        cfg = StorageConfig(path="/tmp/test.json")
        assert cfg.action == "read"

    def test_storage_config_rejects_invalid_action(self):
        with pytest.raises(ValidationError):
            StorageConfig(path="/tmp/test.json", action="delete")
