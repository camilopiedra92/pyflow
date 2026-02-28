from __future__ import annotations

import os


def resolve_openapi_auth(auth):
    """Map OpenApiAuthConfig to ADK auth_scheme + auth_credential.

    Returns (auth_scheme, auth_credential) tuple. Both are None for type='none'.
    """
    match auth.type:
        case "none":
            return None, None
        case "bearer":
            from google.adk.tools.openapi_tool.auth.auth_helpers import (
                token_to_scheme_credential,
            )

            token = os.environ.get(auth.token_env or "", "")
            return token_to_scheme_credential(
                "oauth2Token", "header", "Authorization", token
            )
        case "apikey":
            from google.adk.tools.openapi_tool.auth.auth_helpers import (
                token_to_scheme_credential,
            )

            key = os.environ.get(auth.token_env or "", "")
            return token_to_scheme_credential(
                "apikey", auth.apikey_location, auth.apikey_name, key
            )
        case "oauth2":
            from fastapi.openapi.models import OAuth2, OAuthFlowAuthorizationCode, OAuthFlows
            from google.adk.auth import AuthCredential, AuthCredentialTypes, OAuth2Auth

            auth_scheme = OAuth2(
                flows=OAuthFlows(
                    authorizationCode=OAuthFlowAuthorizationCode(
                        authorizationUrl=auth.authorization_url or "",
                        tokenUrl=auth.token_url or "",
                        scopes=auth.scopes or {},
                    )
                )
            )
            auth_credential = AuthCredential(
                auth_type=AuthCredentialTypes.OAUTH2,
                oauth2=OAuth2Auth(
                    client_id=os.environ.get(auth.client_id_env or "", ""),
                    client_secret=os.environ.get(auth.client_secret_env or "", ""),
                ),
            )
            return auth_scheme, auth_credential
        case _:
            return None, None
