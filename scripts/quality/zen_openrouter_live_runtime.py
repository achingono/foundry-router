"""Isolated Zen/OpenRouter live-verification runtime; never production configuration.

Test-only verification tooling. Credentials live only in process memory, are
cleared on close, and are never logged, persisted, or echoed in results. Only
allow-listed statuses, counts, numeric deltas and acceptance flags leave this
module; prompts, outputs, vectors, raw frames, error bodies and secrets never do.
"""

from __future__ import annotations

import asyncio
import json
import math
import secrets
import time
from http import HTTPStatus
from typing import Any, ClassVar

import httpx
from fastapi import FastAPI, HTTPException, Request
from zen_openrouter_live_budget import (
    CASE_TIMEOUT_SECONDS,
    MAX_FRAME_BYTES,
    MAX_INPUT_BYTES,
    MAX_OBSERVED_BYTES,
    MAX_OUTPUT_TOKENS,
)

from foundry_router.api.adapters.google_schema import load_bounded_json
from foundry_router.api.routes.openai import build_router
from foundry_router.auth import verify_client_auth
from foundry_router.backends import AllowedBackendClient
from foundry_router.config import Settings
from foundry_router.credit import InMemoryCreditStore
from foundry_router.health import InMemoryHealthStore
from foundry_router.metrics import InMemoryMetricsStore
from foundry_router.ratelimit import InMemoryRateLimitStore

PROMPT = "Reply with the word ready."
EMBEDDING_INPUTS = ("first verification sentence", "second verification sentence")
EMBEDDING_VECTOR_COUNT = 2
HTTP_TIMEOUT_SECONDS = 120
CLEANUP_POLLS = 10
CLEANUP_INTERVAL_SECONDS = 1.0

ERROR_TRANSPORT = "transport_rejected"
ERROR_UPSTREAM = "provider_or_protocol_failure"
ERROR_ACCEPTANCE = "acceptance_mismatch"
ERROR_CLEANUP = "cleanup_timeout"
ERROR_BOUND = "bound_exceeded"


class QuietLogger:
    def info(self, *args: Any, **kwargs: Any) -> None:
        pass

    warning = info
    debug = info
    error = info
    exception = info


class IsolatedSettings(Settings):
    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Any,
        init_settings: Any,
        env_settings: Any,
        dotenv_settings: Any,
        file_secret_settings: Any,
    ) -> Any:
        _ = settings_cls, env_settings, dotenv_settings, file_secret_settings
        return (init_settings,)


def _credit_inputs(group: str) -> dict[str, Any]:
    return {
        "backend_cycle_start_day_json": json.dumps({group: 1}),
        "backend_cycle_allowance_usd_json": json.dumps({group: 1000}),
        "backend_initial_estimated_remaining_usd_json": json.dumps({group: 1000}),
    }


def verification_settings(  # noqa: PLR0913 -- explicit owned verification inputs
    *,
    provider: str,
    endpoint: str,
    credential: str,
    deployment: str,
    model: str,
    caller_key: str,
    input_per_million: float,
    output_per_million: float,
    operations: list[str] | None = None,
) -> IsolatedSettings:
    """Single-backend metered test configuration with complete credit inputs."""
    return IsolatedSettings(
        _env_file=None,
        backends_json=json.dumps(
            {
                "v": {
                    "provider": provider,
                    "endpoint": endpoint,
                    "credential": credential,
                    "deployment": deployment,
                    "credit_metered": True,
                    "credit_group": "v",
                    "quota_group": "isolated-live",
                    "supported_operations": operations or ["responses"],
                }
            }
        ),
        models_json=json.dumps({model: {"backends": {"v": 1}}}),
        client_api_keys_json=json.dumps([caller_key]),
        admin_api_keys_json=json.dumps([secrets.token_urlsafe(32)]),
        state_backend="memory",
        rate_limit_backend="memory",
        retry_attempts=0,
        reservation_max_age_seconds=180,
        http_max_connections=1,
        min_credit_reserve_usd=0,
        min_credit_reserve_percent=0,
        pricing_json=json.dumps(
            {
                model: {
                    "input_per_million": input_per_million,
                    "output_per_million": output_per_million,
                }
            }
        ),
        **_credit_inputs("v"),
    )


def _strict_usage(payload: Any, *names: str) -> tuple[int, ...] | None:
    if not isinstance(payload, dict):
        return None
    values = []
    for name in names:
        value = payload.get(name)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            return None
        values.append(value)
    return tuple(values)


class ObservationGuard(httpx.AsyncBaseTransport):
    """Single-dispatch redacted observer around the real upstream transport.

    Reserves the ledger slot before the first provider await. Observes status
    and usage incrementally for streams and bounded-buffered for single-shot
    bodies, enforcing request/response/frame bounds. Records only numeric
    facts; raises (never returns) on any unexpected request or bound breach.
    """

    expected_host = ""
    expected_path = ""

    def __init__(  # noqa: PLR0913 -- explicit owned verification inputs
        self,
        transport: httpx.AsyncBaseTransport,
        *,
        ledger: Any,
        case_id: str,
        credential: str,
        deployment: str,
        stream: bool = False,
    ):
        self.transport = transport
        self.ledger = ledger
        self.case_id = case_id
        self.credential = credential
        self.deployment = deployment
        self.stream = stream
        self.dispatched = False
        self.provider_http_status: int | None = None
        self.usage: tuple[int, int] | None = None
        self.terminated_ok = False
        self.observed_bytes = 0

    def _expected_body(self) -> dict[str, Any]:
        raise NotImplementedError

    def _check_request(self, request: httpx.Request) -> None:
        if (
            self.dispatched
            or request.method != "POST"
            or request.url.scheme != "https"
            or request.url.host != self.expected_host
            or request.url.port not in (None, 443)
            or request.url.path != self.expected_path
            or bool(request.url.query)
            or request.url.userinfo
            or len(request.content) > MAX_INPUT_BYTES + 512
            or request.headers.get("authorization") != "Bearer " + self.credential
            or request.headers.get("accept-encoding") != "identity"
        ):
            raise ValueError("Verification dispatch rejected")
        try:
            body = json.loads(request.content.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise ValueError("Verification dispatch rejected") from exc
        if body != self._expected_body():
            raise ValueError("Verification dispatch rejected")

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self._check_request(request)
        # Durably retain the debit before the first provider await.
        self.ledger.reserve(self.case_id)
        self.dispatched = True
        response = await self.transport.handle_async_request(request)
        self.provider_http_status = response.status_code
        if response.headers.get("content-encoding", "identity").lower() != "identity":
            await response.aclose()
            raise ValueError("Encoded verification response rejected")
        try:
            if self.stream:
                return self._observe_stream(response)
            return await self._observe_single(response)
        except Exception:
            await response.aclose()
            raise

    async def _observe_single(self, response: httpx.Response) -> httpx.Response:
        chunks = bytearray()
        async for chunk in response.aiter_bytes():
            if len(chunks) + len(chunk) > MAX_OBSERVED_BYTES:
                raise ValueError("Verification response bound exceeded")
            chunks.extend(chunk)
        self.observed_bytes = len(chunks)
        self._capture_usage(bytes(chunks), stream=False)
        return httpx.Response(
            response.status_code,
            headers=_safe_headers(response),
            content=bytes(chunks),
        )

    def _observe_stream(self, response: httpx.Response) -> httpx.Response:
        guard = self

        async def observed() -> Any:
            buffer = bytearray()
            frame = bytearray()
            try:
                async for chunk in response.aiter_bytes():
                    guard.observed_bytes += len(chunk)
                    if guard.observed_bytes > MAX_OBSERVED_BYTES:
                        raise ValueError("Verification response bound exceeded")
                    buffer.extend(chunk)
                    while True:
                        event, rest = _split_frame(bytes(buffer))
                        if event is None:
                            break
                        buffer = bytearray(rest)
                        frame.extend(event)
                        if len(frame) > MAX_FRAME_BYTES:
                            raise ValueError("Verification frame bound exceeded")
                        guard._capture_usage(frame, stream=True)
                        frame = bytearray()
                        yield event
                if buffer.strip():
                    guard._capture_usage(bytes(buffer), stream=True, final=True)
            finally:
                await response.aclose()

        return httpx.Response(
            response.status_code, headers=_safe_headers(response), content=observed()
        )

    def _capture_usage(self, payload: bytes, *, stream: bool, final: bool = False) -> None:
        raise NotImplementedError

    async def aclose(self) -> None:
        self.credential = ""
        await self.transport.aclose()


def _safe_headers(response: httpx.Response) -> dict[str, str]:
    return {
        key: value
        for key, value in response.headers.items()
        if key.lower() not in {"content-encoding", "content-length", "transfer-encoding"}
    }


def _split_frame(buffer: bytes) -> tuple[bytes | None, bytes]:
    for delimiter in (b"\r\n\r\n", b"\n\n"):
        index = buffer.find(delimiter)
        if index >= 0:
            return buffer[: index + len(delimiter)], buffer[index + len(delimiter) :]
    return None, buffer


def _parse_event_usage(payload: bytes) -> dict[str, Any] | None:
    text = payload.decode("utf-8", "ignore")
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("data:"):
            continue
        data = stripped[5:].strip()
        if not data or data == "[DONE]":
            continue
        try:
            event = load_bounded_json(data, max_bytes=MAX_FRAME_BYTES)
        except (ValueError, TypeError):
            return None
        if isinstance(event, dict):
            return event
    return None


class ZenGuard(ObservationGuard):
    expected_host = "opencode.ai"
    expected_path = "/zen/v1/responses"

    def _expected_body(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": self.deployment,
            "input": PROMPT,
            "max_output_tokens": MAX_OUTPUT_TOKENS,
        }
        if self.stream:
            body["stream"] = True
        return body

    def _capture_usage(self, payload: bytes, *, stream: bool, final: bool = False) -> None:
        _ = final
        if stream:
            event = _parse_event_usage(payload)
            if event is None:
                return
            if event.get("type") == "response.completed":
                response = event.get("response")
                usage = response.get("usage") if isinstance(response, dict) else None
                counts = _strict_usage(usage, "input_tokens", "output_tokens", "total_tokens")
                if counts is not None and counts[2] == counts[0] + counts[1]:
                    self.usage = (counts[0], counts[1])
                    self.terminated_ok = True
            return
        try:
            body = load_bounded_json(payload.decode("utf-8"), max_bytes=MAX_OBSERVED_BYTES)
        except (ValueError, UnicodeError):
            return
        usage = body.get("usage") if isinstance(body, dict) else None
        counts = _strict_usage(usage, "input_tokens", "output_tokens", "total_tokens")
        if counts is not None and counts[2] == counts[0] + counts[1]:
            self.usage = (counts[0], counts[1])


class OpenRouterGuard(ObservationGuard):
    expected_host = "openrouter.ai"
    expected_path = "/api/v1/chat/completions"

    def _expected_body(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": self.deployment,
            "messages": [{"role": "user", "content": PROMPT}],
            "max_completion_tokens": MAX_OUTPUT_TOKENS,
        }
        if self.stream:
            body["stream"] = True
            body["stream_options"] = {"include_usage": True}
        return body

    def _capture_usage(self, payload: bytes, *, stream: bool, final: bool = False) -> None:
        _ = final
        if stream:
            text = payload.decode("utf-8", "ignore")
            if "[DONE]" in text:
                self.terminated_ok = True
            event = _parse_event_usage(payload)
            if event is None:
                return
            usage = event.get("usage")
            if usage is None:
                return
            counts = _strict_usage(usage, "prompt_tokens", "completion_tokens", "total_tokens")
            if counts is not None and counts[2] == counts[0] + counts[1]:
                self.usage = (counts[0], counts[1])
            return
        try:
            body = load_bounded_json(payload.decode("utf-8"), max_bytes=MAX_OBSERVED_BYTES)
        except (ValueError, UnicodeError):
            return
        usage = body.get("usage") if isinstance(body, dict) else None
        counts = _strict_usage(usage, "prompt_tokens", "completion_tokens", "total_tokens")
        if counts is not None and counts[2] == counts[0] + counts[1]:
            self.usage = (counts[0], counts[1])


async def _read_public_terminal(  # noqa: PLR0911, PLR0912 -- fixed terminal scan
    client: httpx.AsyncClient, *, caller_key: str, stream: bool
) -> tuple[int, dict[str, Any]]:
    """Read router SSE to a single terminal response; failures yield no terminal."""
    if not stream:
        result = await client.post(
            "/openai/v1/responses",
            headers={"api-key": caller_key},
            json={
                "model": "m",
                "input": PROMPT,
                "max_output_tokens": MAX_OUTPUT_TOKENS,
            },
        )
        if result.status_code != HTTPStatus.OK:
            return result.status_code, {}
        try:
            public = result.json()
        except ValueError:
            return result.status_code, {}
        return result.status_code, public if isinstance(public, dict) else {}
    wire = bytearray()
    async with client.stream(
        "POST",
        "/openai/v1/responses",
        headers={"api-key": caller_key},
        json={
            "model": "m",
            "input": PROMPT,
            "max_output_tokens": MAX_OUTPUT_TOKENS,
            "stream": True,
        },
    ) as response:
        if response.status_code != HTTPStatus.OK:
            return response.status_code, {}
        async for chunk in response.aiter_bytes():
            if len(wire) + len(chunk) > MAX_OBSERVED_BYTES:
                raise ValueError("Verification response bound exceeded")
            wire.extend(chunk)
    try:
        text = bytes(wire).decode("utf-8")
    except UnicodeError:
        return HTTPStatus.OK, {}
    terminal: dict[str, Any] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("data:"):
            continue
        payload = stripped[5:].strip()
        if not payload or payload == "[DONE]":
            continue
        try:
            event = load_bounded_json(payload, max_bytes=MAX_FRAME_BYTES)
        except (ValueError, TypeError):
            return HTTPStatus.OK, {}
        if not isinstance(event, dict):
            continue
        if event.get("type") in {"response.failed", "error"}:
            return HTTPStatus.OK, {"failed": True}
        if event.get("type") in {"response.completed", "response.incomplete"}:
            response_body = event.get("response")
            terminal = response_body if isinstance(response_body, dict) else {}
    return HTTPStatus.OK, terminal


def _public_text_present(public: dict[str, Any]) -> bool:
    output = public.get("output")
    if not isinstance(output, list):
        return False
    return any(
        isinstance(part, dict)
        and part.get("type") == "output_text"
        and isinstance(part.get("text"), str)
        and bool(part["text"].strip())
        for item in output
        if isinstance(item, dict) and isinstance(item.get("content"), list)
        for part in item["content"]
    )


def _public_completed(public: dict[str, Any]) -> bool:
    return (
        public.get("status") == "completed"
        and not public.get("error")
        and not public.get("incomplete_details")
    )


async def _poll_cleanup(credit: Any, backend_id: str = "v") -> bool:
    for _ in range(CLEANUP_POLLS):
        live = (
            await credit.live_snapshot(
                [backend_id], min_credit_reserve_usd=0, min_credit_reserve_percent=0
            )
        )[backend_id]
        if live.active_reservations == 0 and live.reserved_inflight_usd == 0:
            return True
        await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
    return False


async def run_live_case(  # noqa: PLR0913, PLR0915, PLR0911, PLR0912 -- fixed verification contract
    *,
    kind: str,
    credential: str,
    ledger: Any,
    case_id: str,
    transport: httpx.AsyncBaseTransport,
    zen_model: str,
    openrouter_model: str,
    embedding_model: str,
    input_per_million: float,
    output_per_million: float,
) -> dict[str, Any]:
    """Execute one fixed verification case; only redacted numerics are returned."""
    started = time.monotonic()
    result: dict[str, Any] = {
        "case_id": case_id,
        "kind": kind,
        "stream": kind.endswith("-stream"),
        "status": "failed",
        "http_status": None,
        "provider_http_status": None,
        "dispatched": False,
        "input_tokens": None,
        "output_tokens": None,
        "usage_matches": False,
        "terminated_ok": False,
        "settlement_matches": False,
        "reservations_cleared": False,
        "synthetic_debit_usd": 0.0,
        "vector_count": 0,
        "dimensions": 0,
        "order_matches": False,
        "vector_values_match": False,
        "error_category": None,
        "elapsed_seconds": 0.0,
    }

    def finish(category: str | None) -> dict[str, Any]:
        result["error_category"] = category
        result["elapsed_seconds"] = round(time.monotonic() - started, 3)
        return result

    if kind.startswith("zen-"):
        provider, endpoint, deployment = (
            "opencode_zen",
            "https://opencode.ai/zen/v1",
            zen_model,
        )
        guard_factory: Any = ZenGuard
        model, operations = "m", ["responses"]
    elif kind == "openrouter-embeddings":
        provider, endpoint, deployment = (
            "openrouter",
            "https://openrouter.ai/api/v1",
            embedding_model,
        )
        guard_factory = OpenRouterEmbeddingsGuard
        model, operations = "e", ["embeddings"]
    elif kind.startswith("openrouter-"):
        provider, endpoint, deployment = (
            "openrouter",
            "https://openrouter.ai/api/v1",
            openrouter_model,
        )
        guard_factory = OpenRouterGuard
        model, operations = "m", ["responses"]
    else:
        return finish(ERROR_TRANSPORT)
    stream = kind.endswith("-stream")
    caller_key = secrets.token_urlsafe(32)
    settings = verification_settings(
        provider=provider,
        endpoint=endpoint,
        credential=credential,
        deployment=deployment,
        model=model,
        caller_key=caller_key,
        input_per_million=input_per_million,
        output_per_million=output_per_million,
        operations=operations,
    )
    guard = guard_factory(
        transport,
        ledger=ledger,
        case_id=case_id,
        credential=credential,
        deployment=deployment,
        stream=stream,
    )
    backend = AllowedBackendClient(settings=settings)
    await backend._client.aclose()
    backend._client = httpx.AsyncClient(
        transport=guard,
        timeout=HTTP_TIMEOUT_SECONDS,
        trust_env=False,
        follow_redirects=False,
        headers={"Accept-Encoding": "identity"},
    )
    credit = InMemoryCreditStore()
    await credit.sync_from_settings(settings)
    quota = InMemoryRateLimitStore()
    await quota.sync_from_settings(settings)
    app = FastAPI()

    async def authenticate(request: Request) -> str:
        if request.headers.get("api-key") != caller_key:
            raise HTTPException(status_code=401, detail="Invalid verification caller")
        request.state.correlation_id = case_id
        request.state.request_key = case_id
        return caller_key

    app.dependency_overrides[verify_client_auth] = authenticate
    app.include_router(
        build_router(
            load_settings_fn=lambda: settings,
            get_backend_client_fn=lambda: backend,
            sleep_fn=asyncio.sleep,
            health_store=InMemoryHealthStore(),
            credit_store=credit,
            metrics_store=InMemoryMetricsStore(),
            rate_limit_store=quota,
            logger=QuietLogger(),
        )
    )
    try:
        try:
            before = (
                await credit.live_snapshot(
                    ["v"], min_credit_reserve_usd=0, min_credit_reserve_percent=0
                )
            )["v"].estimated_remaining_usd
            async with asyncio.timeout(CASE_TIMEOUT_SECONDS):
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app), base_url="http://isolated.test"
                ) as client:
                    if kind == "openrouter-embeddings":
                        status, public = await _read_public_embeddings(client, caller_key)
                    else:
                        status, public = await _read_public_terminal(
                            client, caller_key=caller_key, stream=stream
                        )
        except TimeoutError:
            return finish(ERROR_UPSTREAM)
        except ValueError as exc:
            # Guard rejections and bound breaches carry no secret content.
            if "bound exceeded" in str(exc):
                return finish(ERROR_BOUND)
            return finish(ERROR_TRANSPORT)
        except (OSError, RuntimeError, httpx.HTTPError):
            return finish(ERROR_UPSTREAM)
        result["http_status"] = int(status)
        result["provider_http_status"] = guard.provider_http_status
        result["dispatched"] = guard.dispatched
        if guard.usage is not None:
            result["input_tokens"], result["output_tokens"] = guard.usage
        result["terminated_ok"] = guard.terminated_ok or not stream
        if kind == "openrouter-embeddings":
            accepted = _accept_embeddings(public, guard, result)
        else:
            accepted = _accept_responses(public, guard, result, stream=stream)
        if not accepted:
            return finish(ERROR_ACCEPTANCE)
        try:
            async with asyncio.timeout(CLEANUP_POLLS * CLEANUP_INTERVAL_SECONDS + 5):
                cleared = await _poll_cleanup(credit)
        except TimeoutError:
            return finish(ERROR_CLEANUP)
        result["reservations_cleared"] = cleared
        if not cleared:
            return finish(ERROR_CLEANUP)
        after = (
            await credit.live_snapshot(
                ["v"], min_credit_reserve_usd=0, min_credit_reserve_percent=0
            )
        )["v"].estimated_remaining_usd
        debit = before - after
        expected = (
            result["input_tokens"] * input_per_million
            + result["output_tokens"] * output_per_million
        ) / 1_000_000
        result["synthetic_debit_usd"] = round(debit, 9)
        result["settlement_matches"] = bool(math.isclose(debit, expected, abs_tol=1e-9))
        if not result["settlement_matches"]:
            return finish(ERROR_ACCEPTANCE)
        result["status"] = "passed"
        return finish(None)
    finally:
        await backend.aclose()
        app.dependency_overrides.clear()


async def _read_public_embeddings(
    client: httpx.AsyncClient, caller_key: str
) -> tuple[int, dict[str, Any]]:
    result = await client.post(
        "/openai/v1/embeddings",
        headers={"api-key": caller_key},
        json={"model": "e", "input": list(EMBEDDING_INPUTS)},
    )
    if result.status_code != HTTPStatus.OK:
        return result.status_code, {}
    try:
        public = result.json()
    except ValueError:
        return result.status_code, {}
    return result.status_code, public if isinstance(public, dict) else {}


def _accept_responses(
    public: dict[str, Any], guard: Any, result: dict[str, Any], *, stream: bool
) -> bool:
    _ = stream
    if result["http_status"] != HTTPStatus.OK or not _public_completed(public):
        return False
    if not _public_text_present(public):
        return False
    if guard.usage is None:
        return False
    public_usage = public.get("usage")
    if not isinstance(public_usage, dict):
        return False
    # OpenRouter reports Chat usage names; Zen reports Responses names.
    observed_in = public_usage.get("input_tokens", public_usage.get("prompt_tokens"))
    observed_out = public_usage.get("output_tokens", public_usage.get("completion_tokens"))
    matches = observed_in == guard.usage[0] and observed_out == guard.usage[1]
    result["usage_matches"] = bool(matches)
    return bool(matches and result["terminated_ok"])


def _accept_embeddings(public: dict[str, Any], guard: Any, result: dict[str, Any]) -> bool:
    data = public.get("data")
    vectors: list[list[float]] = []
    if isinstance(data, list) and len(data) == EMBEDDING_VECTOR_COUNT:
        for index, item in enumerate(data):
            if not isinstance(item, dict) or item.get("index") != index:
                return False
            embedding = item.get("embedding")
            if (
                not isinstance(embedding, list)
                or not embedding
                or any(
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not math.isfinite(float(value))
                    for value in embedding
                )
            ):
                return False
            vectors.append([float(value) for value in embedding])
    if len(vectors) != EMBEDDING_VECTOR_COUNT or len(vectors[0]) != len(vectors[1]):
        return False
    result["vector_count"] = EMBEDDING_VECTOR_COUNT
    result["dimensions"] = len(vectors[0])
    result["order_matches"] = bool(
        guard.order_ok
        and guard.vector_count == EMBEDDING_VECTOR_COUNT
        and guard.dimensions == len(vectors[0])
    )
    # Policy: exact element-by-element equality after JSON numeric values are
    # normalized to Python floats. Vectors remain transient and are never persisted.
    result["vector_values_match"] = bool(
        guard.upstream_vectors
        and vectors == guard.upstream_vectors
    )
    if guard.usage is None:
        return False
    public_usage = public.get("usage")
    if not isinstance(public_usage, dict):
        return False
    observed_in = public_usage.get("prompt_tokens")
    matches = observed_in == guard.usage[0]
    result["usage_matches"] = bool(matches)
    result["terminated_ok"] = True
    return bool(matches and result["order_matches"] and result["vector_values_match"])


class OpenRouterEmbeddingsGuard(ObservationGuard):
    expected_host = "openrouter.ai"
    expected_path = "/api/v1/embeddings"
    vector_count = 0
    dimensions = 0
    order_ok = False
    upstream_vectors: ClassVar[list[list[float]]] = []

    def _expected_body(self) -> dict[str, Any]:
        return {
            "model": self.deployment,
            "input": ["first verification sentence", "second verification sentence"],
            "encoding_format": "float",
        }

    def _capture_usage(self, payload: bytes, *, stream: bool, final: bool = False) -> None:
        _ = stream, final
        try:
            body = load_bounded_json(payload.decode("utf-8"), max_bytes=MAX_OBSERVED_BYTES)
        except (ValueError, UnicodeError):
            return
        if not isinstance(body, dict):
            return
        data = body.get("data")
        if isinstance(data, list) and len(data) == EMBEDDING_VECTOR_COUNT:
            vectors = []
            for index, item in enumerate(data):
                if not isinstance(item, dict) or item.get("index") != index:
                    return
                embedding = item.get("embedding")
                if (
                    not isinstance(embedding, list)
                    or not embedding
                    or any(
                        isinstance(value, bool)
                        or not isinstance(value, (int, float))
                        or not math.isfinite(float(value))
                        for value in embedding
                    )
                ):
                    return
                vectors.append(embedding)
            if len(vectors[0]) == len(vectors[1]) and len(vectors[0]) > 0:
                self.vector_count = EMBEDDING_VECTOR_COUNT
                self.dimensions = len(vectors[0])
                self.order_ok = True
                self.upstream_vectors = [[float(value) for value in vector] for vector in vectors]
        usage = body.get("usage")
        counts = _strict_usage(usage, "prompt_tokens", "total_tokens")
        if counts is not None and counts[1] >= counts[0]:
            self.usage = (counts[0], 0)
