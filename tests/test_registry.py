from pyflow.nodes import default_registry


class TestDefaultRegistry:
    def test_has_http(self):
        assert "http" in default_registry.list_types()

    def test_has_transform(self):
        assert "transform" in default_registry.list_types()

    def test_has_condition(self):
        assert "condition" in default_registry.list_types()
