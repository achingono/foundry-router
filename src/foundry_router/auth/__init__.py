"""Authentication dependencies for Foundry Router."""

from __future__ import annotations

import hmac
from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

from foundry_router.config import load_settings


class AuthError(HTTPException):
    """Authentication error with proper headers."""

    def __init__(self, detail: str = "Invalid authentication credentials") -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": 'Bearer realm="foundry-router"'},
        )


# Client authentication (for /openai/v1/* endpoints)
client_api_key_header = APIKeyHeader(name="api-key", auto_error=False)
client_bearer = HTTPBearer(auto_error=False)


async def verify_client_auth(
    api_key: str | None = Security(client_api_key_header),
    bearer: HTTPAuthorizationCredentials | None = Security(client_bearer),
) -> str:
    """Verify client authentication for OpenAI-compatible endpoints.

    Accepts either 'api-key' header or 'Authorization: Bearer <key>' header.
    """
    settings = load_settings()

    # Extract key from either header
    provided_key = None
    if api_key:
        provided_key = api_key
    elif bearer and bearer.scheme.lower() == "bearer":
        provided_key = bearer.credentials

    if not provided_key:
        raise AuthError(
            "Missing authentication: provide 'api-key' header or 'Authorization: Bearer <key>'"
        )

    # Constant-time comparison against valid keys
    for valid_key in settings.client_api_keys:
        if hmac.compare_digest(provided_key, valid_key):
            return provided_key

    raise AuthError("Invalid client API key")


# Admin authentication (for /admin/status endpoint)
admin_api_key_header = APIKeyHeader(name="x-admin-key", auto_error=False)
admin_bearer = HTTPBearer(auto_error=False)


async def verify_admin_auth(
    api_key: str | None = Security(admin_api_key_header),
    bearer: HTTPAuthorizationCredentials | None = Security(admin_bearer),
) -> str:
    """Verify admin authentication for administrative endpoints.

    Accepts either 'x-admin-key' header or 'Authorization: Bearer <key>' header.
    Uses separate key set from client authentication.
    """
    settings = load_settings()

    # Extract key from either header
    provided_key = None
    if api_key:
        provided_key = api_key
    elif bearer and bearer.scheme.lower() == "bearer":
        provided_key = bearer.credentials

    if not provided_key:
        raise AuthError(
            "Missing admin authentication: provide 'x-admin-key' header or "
            "'Authorization: Bearer <key>'"
        )

    # Constant-time comparison against valid admin keys
    for valid_key in settings.admin_api_keys:
        if hmac.compare_digest(provided_key, valid_key):
            return provided_key

    raise AuthError("Invalid admin API key")


# Dependency types for type hints
ClientAuth = Annotated[str, Depends(verify_client_auth)]
AdminAuth = Annotated[str, Depends(verify_admin_auth)]
