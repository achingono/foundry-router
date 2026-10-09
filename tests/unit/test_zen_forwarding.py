"""Unit tests for Zen single-shot pass-through forwarding."""

from __future__ import annotations

import asyncio
import json
import time
from contextlib import suppress
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx

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


def _harness(client: object):
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
    async def test_success_forwards_bytes_unchanged(self) -> None:
        raw = _ok_body()
        request = AsyncMock(
            return_value=httpx.Response(200, content=raw, headers={"content-type": "x"})
        )
        client = SimpleNamespace(request_backend=request)
        env = _harness(client)
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

    async def test_ambiguous_5xx_is_terminal_force_charge_single_dispatch(self) -> None:
        request = AsyncMock(return_value=httpx.Response(500, content=b"boom"))
        client = SimpleNamespace(request_backend=request)
        env = _harness(client)
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

    async def test_pre_output_429_is_failover_eligible(self) -> None:
        request = AsyncMock(return_value=httpx.Response(429, content=b"slow"))
        client = SimpleNamespace(request_backend=request)
        env = _harness(client)
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

    async def test_auth_failure_is_terminal_without_charge(self) -> None:
        request = AsyncMock(return_value=httpx.Response(401, content=b"no"))
        client = SimpleNamespace(request_backend=request)
        env = _harness(client)
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

    async def test_transport_error_force_charges_estimate(self) -> None:
        async def fail(*_args, **_kwargs):
            raise httpx.ConnectError("down")

        client = SimpleNamespace(request_backend=fail)
        env = _harness(client)
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

    async def test_malformed_success_body_force_charges(self) -> None:
        request = AsyncMock(return_value=httpx.Response(200, content=b"not json"))
        client = SimpleNamespace(request_backend=request)
        env = _harness(client)
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

    async def test_expired_deadline_releases_without_dispatch(self) -> None:
        request = AsyncMock(return_value=httpx.Response(200, content=_ok_body()))
        client = SimpleNamespace(request_backend=request)
        env = _harness(client)
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

    async def test_streaming_expired_deadline_does_not_create_upstream_stream(self) -> None:
        stream_backend = AsyncMock()
        client = SimpleNamespace(stream_backend=stream_backend)
        env = _harness(client)
        result = await forwarding._forward_zen_streaming(
            settings=env.settings,
            backend_id="zen_a",
            request_id="req-expired",
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
            reservation_deadline_monotonic=time.monotonic() - 1,
        )
        assert result.confirmed_pre_dispatch is True
        stream_backend.assert_not_called()


class _FakeStreamContext:
    def __init__(
        self, *, status: int = 200, chunks: list[bytes] | None = None, error: bytes = b""
    ) -> None:
        self._status = status
        self._chunks = list(chunks or [])
        self._error = error
        self.closed = False
        self.exit_calls = 0
        self.exit_error: Exception | None = None
        self.upstream = SimpleNamespace(
            status_code=status,
            headers={},
            content=error,
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
        self.exit_calls += 1
        self.closed = True
        if self.exit_error is not None:
            raise self.exit_error
        return False


class TestZenStreaming:
    async def test_success_streams_unchanged_single_dispatch(self) -> None:
        chunks = [
            b'data: {"type":"response.created"}\n\n',
            b'data: {"response":{"usage":{"input_tokens":10,"output_tokens":5}}}\n\n',
        ]
        context = _FakeStreamContext(status=200, chunks=chunks)
        client = SimpleNamespace(stream_backend=lambda *_a, **_k: context)
        env = _harness(client)
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

    async def test_pre_output_500_is_terminal_force_charge(self) -> None:
        context = _FakeStreamContext(status=500, error=b"boom")
        client = SimpleNamespace(stream_backend=lambda *_a, **_k: context)
        env = _harness(client)
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
        env.cooldown.assert_awaited_once()
        assert env.cooldown.await_args.kwargs["state"] == BackendHealthState.ERROR_COOLDOWN

    async def test_pre_output_429_is_failover_eligible(self) -> None:
        context = _FakeStreamContext(status=429, error=b"slow")
        client = SimpleNamespace(stream_backend=lambda *_a, **_k: context)
        env = _harness(client)
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


class TestZenStatusAndStreamingLifecycle:
    async def _forward_stream(self, context: _FakeStreamContext, request_id: str = "req-life"):
        env = _harness(SimpleNamespace(stream_backend=lambda *_a, **_k: context))
        credit = SimpleNamespace(finalize_request=AsyncMock())
        metrics = SimpleNamespace(observe_request=AsyncMock())
        quota = SimpleNamespace(finalize_request=AsyncMock())
        result = await forwarding._forward_zen_streaming(
            settings=env.settings,
            backend_id="zen_a",
            request_id=request_id,
            headers={},
            body={"model": "gpt-5.4", "input": "hi", "stream": True},
            upstream_body={"model": "gpt-5.4", "input": "hi"},
            backend_client=SimpleNamespace(stream_backend=lambda *_a, **_k: context),
            set_backend_active=env.active,
            set_backend_cooldown=env.cooldown,
            api_error=env.api_error,
            credit_store=credit,
            metrics_store=metrics,
            rate_limit_store=quota,
        )
        return result, env, credit, metrics, quota

    async def test_auth_statuses_are_terminal_and_set_error_cooldown(self) -> None:
        for status in (401, 403):
            request = AsyncMock(return_value=httpx.Response(status, content=b"auth denied"))
            client = SimpleNamespace(request_backend=request)
            env = _harness(client)
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
            assert result.response.status_code == status
            assert result.retryable_failure is False
            assert result.force_charge is False
            env.cooldown.assert_awaited_once()
            assert env.cooldown.await_args.kwargs["state"] == BackendHealthState.ERROR_COOLDOWN

            context = _FakeStreamContext(status=status, error=b"auth denied")
            streamed, stream_env, *_ = await self._forward_stream(context, f"auth-{status}")
            assert streamed.response.status_code == status
            assert streamed.retryable_failure is False
            assert streamed.force_charge is False
            stream_env.cooldown.assert_awaited_once()
            assert stream_env.cooldown.await_args.kwargs["state"] == BackendHealthState.ERROR_COOLDOWN
            assert context.exit_calls == 1

    async def test_429_is_the_only_failover_eligible_status(self) -> None:
        context = _FakeStreamContext(status=429, error=b"rate limited")
        result, env, *_ = await self._forward_stream(context, "req-429")
        assert result.response.status_code == 429
        assert result.retryable_failure is True
        env.cooldown.assert_awaited_once()
        assert env.cooldown.await_args.kwargs["state"] == BackendHealthState.QUOTA_COOLDOWN

        request = AsyncMock(return_value=httpx.Response(500, content=b"server error"))
        client = SimpleNamespace(request_backend=request)
        nonstream_env = _harness(client)
        nonstream = await forwarding._forward_zen_non_streaming(
            settings=nonstream_env.settings,
            backend_id="zen_a",
            operation="responses",
            headers={},
            public_body={"model": "gpt-5.4", "input": "hi"},
            upstream_body={"model": "gpt-5.4", "input": "hi"},
            backend_client=client,
            set_backend_active=nonstream_env.active,
            set_backend_cooldown=nonstream_env.cooldown,
            api_error=nonstream_env.api_error,
        )
        assert nonstream.response.status_code == 500
        assert nonstream.retryable_failure is False
        assert nonstream.force_charge is True
        assert nonstream.settlement_cost_usd is not None
        nonstream_env.cooldown.assert_awaited_once()
        assert nonstream_env.cooldown.await_args.kwargs["state"] == BackendHealthState.ERROR_COOLDOWN

    async def test_missing_and_malformed_terminal_usage_settle_conservatively(self) -> None:
        cases = [
            [b'data: {"type":"response.created"}\n\n'],
            [
                b'data: {"type":"response.completed","response":{"usage":{"input_tokens":"bad","output_tokens":-1}}}\n\n'
            ],
            [b'data: {"type":"response.created"}\n\n', b'data: [DONE]\n\n'],
        ]
        for index, chunks in enumerate(cases):
            context = _FakeStreamContext(chunks=chunks)
            result, _, credit, metrics, quota = await self._forward_stream(
                context, f"req-missing-{index}"
            )
            assert result.retryable_failure is False
            _ = [part async for part in result.response.body_iterator]
            credit.finalize_request.assert_awaited_once_with(
                f"req-missing-{index}",
                backend_id="zen_a",
                charge_reserved=True,
                charged_cost_usd=None,
            )
            quota.finalize_request.assert_awaited_once_with(
                f"req-missing-{index}", actual_input_tokens=None
            )
            metrics.observe_request.assert_awaited_once()
            assert context.exit_calls == 1

    async def test_downstream_cancellation_finalizes_once(self) -> None:
        context = _FakeStreamContext(
            chunks=[
                b'data: {"type":"response.created"}\n\n',
                b'data: {"type":"response.completed","response":{"usage":{"input_tokens":10,"output_tokens":5}}}\n\n',
            ]
        )
        result, _, credit, metrics, quota = await self._forward_stream(context, "req-cancel")
        iterator = result.response.body_iterator
        assert await anext(iterator) == b'data: {"type":"response.created"}\n\n'
        await iterator.aclose()
        credit.finalize_request.assert_awaited_once()
        metrics.observe_request.assert_awaited_once()
        quota.finalize_request.assert_awaited_once()
        assert context.exit_calls == 1

    async def test_cleanup_failures_do_not_skip_other_finalizers(self) -> None:
        context = _FakeStreamContext(chunks=[b'data: {"type":"response.created"}\n\n'])
        context.exit_error = RuntimeError("synthetic close failure")
        result, _, credit, metrics, quota = await self._forward_stream(context, "req-cleanup")
        credit.finalize_request.side_effect = RuntimeError("synthetic credit failure")
        metrics.observe_request.side_effect = RuntimeError("synthetic metrics failure")
        with suppress(RuntimeError):
            _ = [part async for part in result.response.body_iterator]
        credit.finalize_request.assert_awaited_once()
        metrics.observe_request.assert_awaited_once()
        quota.finalize_request.assert_awaited_once()
        assert context.exit_calls == 1

    async def test_cancellation_during_pre_output_read_closes_and_settles_estimate(self) -> None:
        class CancelBeforeOutput(_FakeStreamContext):
            async def _aiter_raw(self):
                raise asyncio.CancelledError
                yield b""

        context = CancelBeforeOutput()
        result, env, *_ = await self._forward_stream(context, "req-preoutput-cancel")
        assert result.retryable_failure is False
        assert result.force_charge is True
        assert result.settlement_cost_usd is not None
        assert context.exit_calls == 1
        env.cooldown.assert_awaited_once()
        assert env.cooldown.await_args.kwargs["state"] == BackendHealthState.ERROR_COOLDOWN
