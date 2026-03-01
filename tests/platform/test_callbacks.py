from __future__ import annotations

import pytest

from pyflow.platform.callbacks import resolve_callback


class TestFQNCallbackResolution:
    def test_resolve_none_returns_none(self):
        assert resolve_callback(None) is None

    def test_resolve_empty_returns_none(self):
        assert resolve_callback("") is None

    def test_resolve_stdlib_function(self):
        """FQN for a stdlib function should resolve."""
        result = resolve_callback("json.dumps")
        import json

        assert result is json.dumps

    def test_resolve_os_function(self):
        """FQN for os.path.exists should resolve."""
        result = resolve_callback("os.path.exists")
        import os.path

        assert result is os.path.exists

    def test_resolve_bad_module_raises(self):
        """FQN with non-existent module should raise ImportError."""
        with pytest.raises(ModuleNotFoundError):
            resolve_callback("nonexistent_module.func")

    def test_resolve_bad_attr_raises(self):
        """FQN with non-existent attribute should raise AttributeError."""
        with pytest.raises(AttributeError):
            resolve_callback("json.nonexistent_function")


