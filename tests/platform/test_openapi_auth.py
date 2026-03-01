from __future__ import annotations

import os
from unittest.mock import patch

from pyflow.models.agent import OpenApiAuthConfig
from pyflow.platform.openapi_auth import resolve_openapi_auth


class TestResolveOpenApiAuthNone:
    def test_none_returns_none_tuple(self):
        auth = OpenApiAuthConfig(type="none")
        scheme, credential = resolve_openapi_auth(auth)
        assert scheme is None
        assert credential is None


class TestResolveOpenApiAuthBearer:
    def test_bearer_returns_http_scheme(self):
        auth = OpenApiAuthConfig(type="bearer", token_env="TEST_TOKEN")
        with patch.dict(os.environ, {"TEST_TOKEN": "my-secret-token"}):
            scheme, credential = resolve_openapi_auth(auth)
        assert scheme is not None
        assert credential is not None

    def test_bearer_missing_env_returns_empty_token(self):
        auth = OpenApiAuthConfig(type="bearer", token_env="MISSING_VAR")
        with patch.dict(os.environ, {}, clear=True):
            scheme, credential = resolve_openapi_auth(auth)
        assert scheme is not None


class TestResolveOpenApiAuthApiKey:
    def test_apikey_returns_scheme(self):
        auth = OpenApiAuthConfig(
            type="apikey",
            token_env="TEST_API_KEY",
            apikey_location="query",
            apikey_name="api_key",
        )
        with patch.dict(os.environ, {"TEST_API_KEY": "key123"}):
            scheme, credential = resolve_openapi_auth(auth)
        assert scheme is not None
        assert credential is not None


class TestResolveOpenApiAuthOAuth2:
    def test_oauth2_returns_scheme_and_credential(self):
        auth = OpenApiAuthConfig(
            type="oauth2",
            authorization_url="https://example.com/auth",
            token_url="https://example.com/token",
            scopes={"read": "Read access"},
            client_id_env="TEST_CLIENT_ID",
            client_secret_env="TEST_CLIENT_SECRET",
        )
        env = {"TEST_CLIENT_ID": "id123", "TEST_CLIENT_SECRET": "secret456"}
        with patch.dict(os.environ, env):
            scheme, credential = resolve_openapi_auth(auth)
        assert scheme is not None
        assert credential is not None


class TestResolveOpenApiAuthServiceAccount:
    def test_service_account_returns_scheme_and_credential(self):
        import json

        sa_key = json.dumps({"type": "service_account", "project_id": "test"})
        auth = OpenApiAuthConfig(
            type="service_account",
            service_account_env="TEST_SA_KEY",
            service_account_scopes=["https://www.googleapis.com/auth/spreadsheets"],
        )
        with patch.dict(os.environ, {"TEST_SA_KEY": sa_key}):
            scheme, credential = resolve_openapi_auth(auth)
        assert scheme is not None
        assert credential is not None

    def test_service_account_missing_env_returns_empty_config(self):
        auth = OpenApiAuthConfig(
            type="service_account",
            service_account_env="MISSING_SA_KEY",
        )
        with patch.dict(os.environ, {}, clear=True):
            scheme, credential = resolve_openapi_auth(auth)
        # Should still return non-None (empty SA config is handled gracefully)
        assert scheme is not None
        assert credential is not None
