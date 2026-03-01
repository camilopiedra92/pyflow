from __future__ import annotations

from pyflow.models.agent import OpenApiAuthConfig, OpenApiToolConfig


class TestOpenApiAuthConfig:
    def test_default_none(self):
        auth = OpenApiAuthConfig()
        assert auth.type == "none"
        assert auth.token_env is None

    def test_bearer(self):
        auth = OpenApiAuthConfig(type="bearer", token_env="PYFLOW_YNAB_API_TOKEN")
        assert auth.type == "bearer"
        assert auth.token_env == "PYFLOW_YNAB_API_TOKEN"

    def test_apikey(self):
        auth = OpenApiAuthConfig(
            type="apikey",
            token_env="PYFLOW_MY_API_KEY",
            apikey_location="query",
            apikey_name="api_key",
        )
        assert auth.apikey_location == "query"
        assert auth.apikey_name == "api_key"

    def test_apikey_defaults(self):
        auth = OpenApiAuthConfig(type="apikey", token_env="KEY")
        assert auth.apikey_location == "query"
        assert auth.apikey_name == "apikey"

    def test_oauth2(self):
        auth = OpenApiAuthConfig(
            type="oauth2",
            authorization_url="https://accounts.example.com/auth",
            token_url="https://accounts.example.com/token",
            scopes={"read": "Read access"},
            client_id_env="PYFLOW_CLIENT_ID",
            client_secret_env="PYFLOW_CLIENT_SECRET",
        )
        assert auth.type == "oauth2"
        assert auth.scopes == {"read": "Read access"}


class TestOpenApiToolConfig:
    def test_basic_spec(self):
        config = OpenApiToolConfig(spec="specs/petstore.yaml")
        assert config.spec == "specs/petstore.yaml"
        assert config.name_prefix is None
        assert config.tool_filter is None
        assert config.auth.type == "none"

    def test_with_prefix_and_auth(self):
        config = OpenApiToolConfig(
            spec="specs/ynab.json",
            name_prefix="ynab",
            auth=OpenApiAuthConfig(type="bearer", token_env="PYFLOW_YNAB_TOKEN"),
        )
        assert config.name_prefix == "ynab"
        assert config.auth.type == "bearer"

    def test_tool_filter_list(self):
        config = OpenApiToolConfig(
            spec="specs/petstore.yaml",
            tool_filter=["getUsers", "createUser"],
        )
        assert config.tool_filter == ["getUsers", "createUser"]

    def test_tool_filter_fqn_string(self):
        config = OpenApiToolConfig(
            spec="specs/petstore.yaml",
            tool_filter="mypackage.filters.my_predicate",
        )
        assert config.tool_filter == "mypackage.filters.my_predicate"

    def test_tool_filter_default_none(self):
        config = OpenApiToolConfig(spec="specs/petstore.yaml")
        assert config.tool_filter is None


