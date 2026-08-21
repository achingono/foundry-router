"""Backend HTTP client with allow-list enforcement for Foundry Router."""

from __future__ import annotations

from typing import Any

import httpx

from foundry_router.config import load_settings


class SecurityError(Exception):
    """Raised when a security policy is violated."""


class AllowedBackendClient:
    """HTTP client restricted to configured HTTPS origins and base paths."""

    def __init__(self) -> None:
        self._settings = load_settings()
        self._allowed_hostnames = self._settings.get_allowed_hostnames()
        self._allowed_targets = {
            config.endpoint.host: httpx.URL(str(config.endpoint))
            for config in self._settings.backends.values()
        }
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(60.0, connect=10.0),
            follow_redirects=False,
        )

    @property
    def allowed_hostnames(self) -> set[str]:
        return self._allowed_hostnames.copy()

    def _validate_url(self, url: str | httpx.URL) -> None:
        """Validate that the target URL stays within a configured backend target."""
        parsed = httpx.URL(url) if isinstance(url, str) else url
        hostname = parsed.host
        configured = self._allowed_targets.get(hostname)
        if configured is None:
            raise SecurityError(
                f"Outbound request to '{hostname}' blocked: not in configured backend allow-list. "
                f"Allowed: {sorted(self._allowed_hostnames)}"
            )
        if parsed.scheme != "https" or parsed.username or parsed.password:
            raise SecurityError("Outbound request must use HTTPS without URL credentials")
        parsed_port = parsed.port or (443 if parsed.scheme == "https" else None)
        configured_port = configured.port or (443 if configured.scheme == "https" else None)
        if parsed_port != configured_port:
            raise SecurityError("Outbound request port does not match configured backend")

        configured_path = configured.path.rstrip("/")
        requested_path = parsed.path.rstrip("/")
        if configured_path and not (
            requested_path == configured_path or requested_path.startswith(f"{configured_path}/")
        ):
            raise SecurityError("Outbound request path is outside configured backend base path")
        if parsed.fragment:
            raise SecurityError("Outbound request must not contain a URL fragment")

    def _sanitize_headers(self, headers: dict[str, str] | None) -> dict[str, str] | None:
        """Remove sensitive headers before forwarding to backend."""
        if not headers:
            return None

        sensitive = {
            "authorization",
            "api-key",
            "x-api-key",
            "apikey",
            "cookie",
            "set-cookie",
            "proxy-authorization",
            "x-forwarded-for",
            "x-forwarded-proto",
            "x-forwarded-host",
            "forwarded",
        }

        return {k: v for k, v in headers.items() if k.lower() not in sensitive}

    def _validate_request_kwargs(self, kwargs: dict[str, Any]) -> None:
        if kwargs.get("follow_redirects"):
            raise SecurityError("Redirects are disabled for backend requests")
        if kwargs.get("auth") is not None or kwargs.get("cookies") is not None:
            raise SecurityError("Request auth and cookies are not accepted by the backend client")
        params = kwargs.get("params")
        if isinstance(params, dict) and any(
            str(key).lower() in {"api-key", "authorization", "token", "secret"} for key in params
        ):
            raise SecurityError("Sensitive query parameters are not accepted by the backend client")

    async def request(
        self,
        method: str,
        url: str | httpx.URL,
        *,
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        """Make an HTTP request to an allowed backend."""
        self._validate_url(url)
        self._validate_request_kwargs(kwargs)

        sanitized_headers = self._sanitize_headers(headers)
        return await self._client.request(method, url, headers=sanitized_headers, **kwargs)

    async def get(self, url: str | httpx.URL, **kwargs: Any) -> httpx.Response:
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str | httpx.URL, **kwargs: Any) -> httpx.Response:
        return await self.request("POST", url, **kwargs)

    async def put(self, url: str | httpx.URL, **kwargs: Any) -> httpx.Response:
        return await self.request("PUT", url, **kwargs)

    async def patch(self, url: str | httpx.URL, **kwargs: Any) -> httpx.Response:
        return await self.request("PATCH", url, **kwargs)

    async def delete(self, url: str | httpx.URL, **kwargs: Any) -> httpx.Response:
        return await self.request("DELETE", url, **kwargs)

    def stream(
        self,
        method: str,
        url: str | httpx.URL,
        *,
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Stream a request to an allowed backend."""
        self._validate_url(url)
        self._validate_request_kwargs(kwargs)
        sanitized_headers = self._sanitize_headers(headers)
        return self._client.stream(method, url, headers=sanitized_headers, **kwargs)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> AllowedBackendClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.aclose()


# Global client instance (initialized at startup)
_backend_client: AllowedBackendClient | None = None


def get_backend_client() -> AllowedBackendClient:
    """Get the global backend client instance."""
    global _backend_client
    if _backend_client is None:
        _backend_client = AllowedBackendClient()
    return _backend_client


async def close_backend_client() -> None:
    """Close the global backend client."""
    global _backend_client
    if _backend_client is not None:
        await _backend_client.aclose()
        _backend_client = None
