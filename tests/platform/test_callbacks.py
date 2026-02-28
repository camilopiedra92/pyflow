from __future__ import annotations

from pyflow.platform.callbacks import register_callback, resolve_callback, CALLBACK_REGISTRY


class TestCallbackRegistry:
    def test_register_and_resolve(self):
        async def my_cb(ctx):
            pass

        register_callback("test_cb", my_cb)
        assert resolve_callback("test_cb") is my_cb
        # Cleanup
        del CALLBACK_REGISTRY["test_cb"]

    def test_resolve_unknown_returns_none(self):
        assert resolve_callback("nonexistent") is None

    def test_resolve_none_returns_none(self):
        assert resolve_callback(None) is None
