from __future__ import annotations

import pytest

from pyflow.platform.callbacks import resolve_tool_predicate


class TestResolveToolPredicate:
    def test_valid_callable(self) -> None:
        """Resolving a valid callable FQN returns the callable."""
        predicate = resolve_tool_predicate("os.path.exists")
        assert callable(predicate)

    def test_non_callable_raises_type_error(self) -> None:
        """Resolving a non-callable FQN raises TypeError."""
        with pytest.raises(TypeError, match="did not resolve to a callable"):
            resolve_tool_predicate("os.sep")

    def test_bad_module_raises(self) -> None:
        """Resolving a FQN with non-existent module raises."""
        with pytest.raises(ModuleNotFoundError):
            resolve_tool_predicate("nonexistent_module.func")
