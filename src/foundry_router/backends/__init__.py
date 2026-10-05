"""Backend HTTP client with allow-list enforcement for Foundry Router."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx

from foundry_router.config import load_settings


class SecurityError(Exception):
    """Raised when a security policy is violated."""


MAX_GOOGLE_RESPONSE_BYTES = 4 * 1024 * 1024


class AllowedBackendClient:
    """HTTP client restricted to configured HTTPS origins and base paths."""

    def __init__(self) -> None:
        self._settings = load_settings()
        self._allowed_hostnames = self._settings.get_allowed_hostnames()
        self._allowed_targets = {
            backend_id: httpx.URL(str(config.endpoint))
            for backend_id, config in self._settings.backends.items()
        }
        # Phase 07: Configurable connection pool with keep-alive tuning
        limits = httpx.Limits(
            max_connections=self._settings.http_max_connections,
            max_keepalive_connections=self._settings.http_max_keepalive_connections,
            keepalive_expiry=self._settings.http_keepalive_expiry_seconds,
        )
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(60.0, connect=10.0),
            follow_redirects=False,
            limits=limits,
            http2=self._settings.http2_enabled,  # Enable HTTP/2 multiplexing if configured
        )

    @property
    def allowed_hostnames(self) -> set[str]:
        return self._allowed_hostnames.copy()

    def _validate_url(self, url: str | httpx.URL, backend_id: str | None = None) -> None:
        """Validate that the target URL stays within a configured backend target."""
        parsed = httpx.URL(url) if isinstance(url, str) else url
        if backend_id is not None:
            configured = self._allowed_targets.get(backend_id)
            if configured is None:
                raise SecurityError(f"Unknown backend '{backend_id}'")
            configured_targets = [configured]
        else:
            configured_targets = list(self._allowed_targets.values())
        if not configured_targets:
            raise SecurityError(
                f"Outbound request to '{parsed.host}' blocked: not in configured "
                "backend allow-list. "
                f"Allowed: {sorted(self._allowed_hostnames)}"
            )
        for configured in configured_targets:
            if parsed.host != configured.host or parsed.scheme != configured.scheme:
                continue
            if parsed.username or parsed.password or parsed.fragment:
                break
            parsed_port = parsed.port or (443 if parsed.scheme == "https" else None)
            configured_port = configured.port or (443 if configured.scheme == "https" else None)
            if parsed_port != configured_port:
                continue
            configured_path = configured.path.rstrip("/")
            requested_path = parsed.path.rstrip("/")
            if (
                not configured_path
                or requested_path == configured_path
                or (requested_path.startswith(f"{configured_path}/"))
            ):
                return
        raise SecurityError(
            f"Outbound request to '{parsed.host}' blocked: not in configured backend allow-list"
        )

    def _sanitize_headers(self, headers: dict[str, str] | None) -> dict[str, str] | None:
        """Remove sensitive headers before forwarding to backend."""
        if not headers:
            return None

        sensitive = {
            "authorization",
            "api-key",
            "x-api-key",
            "apikey",
            "x-goog-api-key",
            "cookie",
            "set-cookie",
            "proxy-authorization",
            "x-forwarded-for",
            "x-forwarded-proto",
            "x-forwarded-host",
            "forwarded",
            "connection",
            "keep-alive",
            "proxy-authenticate",
            "te",
            "trailer",
            "transfer-encoding",
            "upgrade",
        }

        return {k: v for k, v in headers.items() if k.lower() not in sensitive}

    def _google_operation(self, operation: str) -> str:
        """Map router operations onto Google's OpenAI-compatible surface.

        Google AI Studio implements ``chat/completions``, ``embeddings`` and
        ``models`` but not OpenAI's proprietary ``responses`` endpoint. Route
        ``responses`` to ``chat/completions`` as the closest compatible
        operation; payload shape differences beyond ``model`` remain a
        documented limitation.
        """
        normalized = operation.lstrip("/").replace("//", "/")
        if normalized == "responses":
            return "chat/completions"
        return normalized

    def prepare_upstream_payload(
        self, backend_id: str, body: dict[str, Any], operation: str = "responses"
    ) -> dict[str, Any]:
        """Return a copy of ``body`` with the provider deployment substituted.

        The router routes on the logical model alias (e.g. ``gpt-5.4``); the
        upstream provider must receive its own deployment/model id
        (e.g. ``gemini-1.5-flash`` in ``config.deployment``).
        """
        config = self._settings.backends.get(backend_id)
        if config is None:
            raise ValueError(f"Unknown backend '{backend_id}'")
        out = dict(body)
        if config.deployment and (
            config.provider == "google_ai_studio"
            or (config.provider == "azure_foundry" and operation == "responses")
        ):
            out["model"] = config.deployment
        return out

    def _backend_url(self, backend_id: str, operation: str) -> httpx.URL:
        config = self._settings.backends.get(backend_id)
        if config is None:
            raise ValueError(f"Unknown backend '{backend_id}'")
        base = httpx.URL(str(config.endpoint))
        if config.provider == "google_ai_studio":
            if not config.deployment:
                raise ValueError(f"Backend '{backend_id}' has no Google model configured")
            effective_operation = self._google_operation(operation)
            # Avoid accidental double compatibility suffixes when the operator
            # configures the endpoint with the compat root already included.
            base_path = base.path.rstrip("/")
            compat_root = "/v1beta/openai"
            base_path = base_path.removesuffix(compat_root)
            path = f"{base_path}{compat_root}/{effective_operation.lstrip('/')}"
            return base.copy_with(path=path)

        if not config.deployment:
            raise ValueError(f"Backend '{backend_id}' has no deployment configured")
        if operation == "responses":
            return base.copy_with(path=f"{base.path.rstrip('/')}/openai/v1/responses")
        path = (
            f"{base.path.rstrip('/')}/openai/deployments/"
            f"{quote(config.deployment, safe='')}/{operation}"
        )
        return base.copy_with(path=path, params={"api-version": config.api_version})

    def _backend_headers(self, backend_id: str, headers: dict[str, str] | None) -> dict[str, str]:
        config = self._settings.backends.get(backend_id)
        if config is None:
            raise ValueError(f"Unknown backend '{backend_id}'")
        safe_headers = self._sanitize_headers(headers) or {}
        if config.provider == "google_ai_studio":
            # Documented OpenAI-compat auth is `Authorization: Bearer <key>`
            # (verified 2026-10-05). Strip inbound auth above; never forward it.
            safe_headers["authorization"] = f"Bearer {config.credential}"
            return safe_headers
        safe_headers["api-key"] = config.credential
        return safe_headers

    async def request_backend(
        self,
        backend_id: str,
        operation: str,
        *,
        method: str = "POST",
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        """Request a configured deployment with its server-side credential."""
        url = self._backend_url(backend_id, operation)
        self._validate_url(url, backend_id)
        self._validate_request_kwargs(kwargs)
        if isinstance(kwargs.get("json"), dict):
            kwargs = {
                **kwargs,
                "json": self.prepare_upstream_payload(backend_id, kwargs["json"], operation),
            }
        return await self._client.request(
            method, url, headers=self._backend_headers(backend_id, headers), **kwargs
        )

    def stream_backend(
        self,
        backend_id: str,
        operation: str,
        *,
        method: str = "POST",
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Open a streaming request to a configured deployment."""
        url = self._backend_url(backend_id, operation)
        self._validate_url(url, backend_id)
        self._validate_request_kwargs(kwargs)
        if isinstance(kwargs.get("json"), dict):
            kwargs = {
                **kwargs,
                "json": self.prepare_upstream_payload(backend_id, kwargs["json"], operation),
            }
        return self._client.stream(
            method, url, headers=self._backend_headers(backend_id, headers), **kwargs
        )

    def _validate_request_kwargs(self, kwargs: dict[str, Any]) -> None:
        if kwargs.get("follow_redirects"):
            raise SecurityError("Redirects are disabled for backend requests")
        if kwargs.get("auth") is not None or kwargs.get("cookies") is not None:
            raise SecurityError("Request auth and cookies are not accepted by the backend client")

        params = kwargs.get("params")
        sensitive_param_names = {
            "api-key",
            "authorization",
            "token",
            "secret",
            "key",
            "x-api-key",
            "x-goog-api-key",
            "apikey",
        }

        if params is None:
            return

        try:
            normalized_params = httpx.QueryParams(params)
        except Exception as exc:  # pragma: no cover - validation guard only
            raise SecurityError("Invalid query parameter payload") from exc

        if any(str(key).lower() in sensitive_param_names for key in normalized_params):
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
