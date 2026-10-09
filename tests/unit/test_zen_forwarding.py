"""Unit tests for Zen single-shot pass-through forwarding."""

from __future__ import annotations

import json
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from foundry_router import forwarding
from foundry_router.config import Settings
from foundry_router.health import BackendHealthState


def _settings() -> Settings:
    return Settings(
        backends_json=json.dumps(
            {
                "zen_a": {
                    "provider": "opencode_zen",
                    "endpoint": "https://opencode.ai/zen/v1",
                    "credential": "synthetic-zen-key",
                    "deployment": "gpt-5.4",
                }
            }
        ),
        models_json='{"gpt-5.4": {"backends": {"zen_a": 1.0}}}',
        client_api_keys_json='["client-key"]',
        admin_api_keys_json='["admin-key"]',
        pricing_json='{"gpt-5.4": {"input_per_million": 1.0, "output_per_million": 2.0}}',
        backend_cycle_start_day_json="{}",
        retry_attempts=5,
    )


def _harness(monkeypatch, client: object):
    settings = _settings()
    active = AsyncMock()
    cooldown = AsyncMock()

    async def get_client():
        return client

    return SimpleNamespace(
        settings=settings,
        active=active,
        cooldown=cooldown,
        get_client=get_client,
        api_error=lambda status, message, code: (status, message, code),
    )


def _ok_body() -> bytes:
    return json.dumps(
        {
            "id": "resp_1",
            "model": "gpt-5.4",
            "output": [],
            "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
        }
    ).encode()


class TestZenNonStreaming:
    async def test_success_forwards_bytes_unchanged(self, monkeypatch) -> None:
        raw = _ok_body()
        request = AsyncMock(
            return_value=httpx.Response(200, content=raw, headers={"content-type": "x"})
        )
        client = SimpleNamespace(request_backend=request)
        env = _harness(monkeypatch, client)
        result = await forwarding._forward_zen_non_streaming(
            settings=env.settings,
            backend_id="zen_a",
            operation="responses",
            headers={},
            public_body={"model": "gpt-5.4", "input": "hi"},
            upstream_body={"model": "gpt-5.4", "input": "hi"},
            backend_client=client,
            set_backend_active=env.active,
            set_backend_cooldown=env.cooldown,
            api_error=env.api_error,
        )
        assert result.retryable_failure is False
        assert result.force_charge is False
        assert result.response.body == raw
        assert result.response.status_code == 200
        env.active.assert_awaited_once_with("zen_a")
        request.assert_awaited_once()

    async def test_ambiguous_5xx_is_terminal_force_charge_single_dispatch(
        self, monkeypatch
    ) -> None:
        request = AsyncMock(return_value=httpx.Response(500, content=b"boom"))
        client = SimpleNamespace(request_backend=request)
        env = _harness(monkeypatch, client)
        result = await forwarding._forward_zen_non_streaming(
            settings=env.settings,
            backend_id="zen_a",
            operation="responses",
            headers={},
            public_body={"model": "gpt-5.4", "input": "hi"},
            upstream_body={"model": "gpt-5.4", "input": "hi"},
            backend_client=client,
            set_backend_active=env.active,
            set_backend_cooldown=env.cooldown,
            api_error=env.api_error,
        )
        assert result.retryable_failure is False
        assert result.force_charge is True
        assert result.settlement_cost_usd is not None
        request.assert_awaited_once()
        env.cooldown.assert_awaited_once()
        assert env.cooldown.await_args.kwargs["state"] == BackendHealthState.ERROR_COOLDOWN

    async def test_pre_output_429_is_failover_eligible(self, monkeypatch) -> None:
        request = AsyncMock(return_value=httpx.Response(429, content=b"slow"))
        client = SimpleNamespace(request_backend=request)
        env = _harness(monkeypatch, client)
        result = await forwarding._forward_zen_non_streaming(
            settings=env.settings,
            backend_id="zen_a",
            operation="responses",
            headers={},
            public_body={"model": "gpt-5.4", "input": "hi"},
            upstream_body={"model": "gpt-5.4", "input": "hi"},
            backend_client=client,
            set_backend_active=env.active,
            set_backend_cooldown=env.cooldown,
            api_error=env.api_error,
        )
        assert result.retryable_failure is True
        assert result.force_charge is False
        request.assert_awaited_once()
        assert env.cooldown.await_args.kwargs["state"] == BackendHealthState.QUOTA_COOLDOWN

    async def test_auth_failure_is_terminal_without_charge(self, monkeypatch) -> None:
        request = AsyncMock(return_value=httpx.Response(401, content=b"no"))
        client = SimpleNamespace(request_backend=request)
        env = _harness(monkeypatch, client)
        result = await forwarding._forward_zen_non_streaming(
            settings=env.settings,
            backend_id="zen_a",
            operation="responses",
            headers={},
            public_body={"model": "gpt-5.4", "input": "hi"},
            upstream_body={"model": "gpt-5.4", "input": "hi"},
            backend_client=client,
            set_backend_active=env.active,
            set_backend_cooldown=env.cooldown,
            api_error=env.api_error,
        )
        assert result.retryable_failure is False
        assert result.force_charge is False
        request.assert_awaited_once()

    async def test_transport_error_force_charges_estimate(self, monkeypatch) -> None:
        async def fail(*args, **kwargs):
            raise httpx.ConnectError("down")

        client = SimpleNamespace(request_backend=fail)
        env = _harness(monkeypatch, client)
        result = await forwarding._forward_zen_non_streaming(
            settings=env.settings,
            backend_id="zen_a",
            operation="responses",
            headers={},
            public_body={"model": "gpt-5.4", "input": "hi"},
            upstream_body={"model": "gpt-5.4", "input": "hi"},
            backend_client=client,
            set_backend_active=env.active,
            set_backend_cooldown=env.cooldown,
            api_error=env.api_error,
        )
        assert result.retryable_failure is False
        assert result.force_charge is True
        assert result.settlement_cost_usd is not None

    async def test_malformed_success_body_force_charges(self, monkeypatch) -> None:
        request = AsyncMock(return_value=httpx.Response(200, content=b"not json"))
        client = SimpleNamespace(request_backend=request)
        env = _harness(monkeypatch, client)
        result = await forwarding._forward_zen_non_streaming(
            settings=env.settings,
            backend_id="zen_a",
            operation="responses",
            headers={},
            public_body={"model": "gpt-5.4", "input": "hi"},
            upstream_body={"model": "gpt-5.4", "input": "hi"},
            backend_client=client,
            set_backend_active=env.active,
            set_backend_cooldown=env.cooldown,
            api_error=env.api_error,
        )
        assert result.retryable_failure is False
        assert result.force_charge is True

    async def test_expired_deadline_releases_without_dispatch(
        self, monkeypatch
    ) -> None:
        request = AsyncMock(return_value=httpx.Response(200, content=_ok_body()))
        client = SimpleNamespace(request_backend=request)
        env = _harness(monkeypatch, client)
        result = await forwarding._forward_zen_non_streaming(
            settings=env.settings,
            backend_id="zen_a",
            operation="responses",
            headers={},
            public_body={"model": "gpt-5.4", "input": "hi"},
            upstream_body={"model": "gpt-5.4", "input": "hi"},
            backend_client=client,
            set_backend_active=env.active,
            set_backend_cooldown=env.cooldown,
            api_error=env.api_error,
            reservation_deadline_monotonic=time.monotonic() - 1,
        )
        assert result.confirmed_pre_dispatch is True
        request.assert_not_awaited()


class _FakeStreamContext:
    def __init__(
        self, *, status: int = 200, chunks: list[bytes] | None = None, error: bytes = b""
    ) -> None:
        self._status = status
        self._chunks = list(chunks or [])
        self._error = error
        self.closed = False
        self.upstream = SimpleNamespace(
            status_code=status,
            headers={},
            aread=self._aread,
            aiter_raw=self._aiter_raw,
        )

    async def _aread(self) -> bytes:
        return self._error

    async def _aiter_raw(self):
        for chunk in self._chunks:
            yield chunk

    async def __aenter__(self):
        return self.upstream

    async def __aexit__(self, *args):
        self.closed = True
        return False


class TestZenStreaming:
    async def test_success_streams_unchanged_single_dispatch(
        self, monkeypatch
    ) -> None:
        chunks = [
            b'data: {"type":"response.created"}\n\n',
            b'data: {"response":{"usage":{"input_tokens":10,"output_tokens":5}}}\n\n',
        ]
        context = _FakeStreamContext(status=200, chunks=chunks)
        client = SimpleNamespace(stream_backend=lambda *a, **k: context)
        env = _harness(monkeypatch, client)
        result = await forwarding._forward_zen_streaming(
            settings=env.settings,
            backend_id="zen_a",
            request_id="req-1",
            headers={},
            body={"model": "gpt-5.4", "input": "hi", "stream": True},
            upstream_body={"model": "gpt-5.4", "input": "hi"},
            backend_client=client,
            set_backend_active=env.active,
            set_backend_cooldown=env.cooldown,
            api_error=env.api_error,
            credit_store=SimpleNamespace(finalize_request=AsyncMock()),
            metrics_store=SimpleNamespace(observe_request=AsyncMock()),
            rate_limit_store=None,
        )
        assert result.retryable_failure is False
        assert result.response.status_code == 200
        env.active.assert_awaited_once_with("zen_a")

    async def test_pre_output_500_is_terminal_force_charge(self, monkeypatch) -> None:
        context = _FakeStreamContext(status=500, error=b"boom")
        client = SimpleNamespace(stream_backend=lambda *a, **k: context)
        env = _harness(monkeypatch, client)
        result = await forwarding._forward_zen_streaming(
            settings=env.settings,
            backend_id="zen_a",
            request_id="req-2",
            headers={},
            body={"model": "gpt-5.4", "input": "hi", "stream": True},
            upstream_body={"model": "gpt-5.4", "input": "hi"},
            backend_client=client,
            set_backend_active=env.active,
            set_backend_cooldown=env.cooldown,
            api_error=env.api_error,
            credit_store=SimpleNamespace(finalize_request=AsyncMock()),
            metrics_store=SimpleNamespace(observe_request=AsyncMock()),
            rate_limit_store=None,
        )
        assert result.retryable_failure is False
        assert result.force_charge is True
        assert context.closed is True

    async def test_pre_output_429_is_failover_eligible(self, monkeypatch) -> None:
        context = _FakeStreamContext(status=429, error=b"slow")
        client = SimpleNamespace(stream_backend=lambda *a, **k: context)
        env = _harness(monkeypatch, client)
        result = await forwarding._forward_zen_streaming(
            settings=env.settings,
            backend_id="zen_a",
            request_id="req-3",
            headers={},
            body={"model": "gpt-5.4", "input": "hi", "stream": True},
            upstream_body={"model": "gpt-5.4", "input": "hi"},
            backend_client=client,
            set_backend_active=env.active,
            set_backend_cooldown=env.cooldown,
            api_error=env.api_error,
            credit_store=SimpleNamespace(finalize_request=AsyncMock()),
            metrics_store=SimpleNamespace(observe_request=AsyncMock()),
            rate_limit_store=None,
        )
        assert result.retryable_failure is True
        assert context.closed is True
