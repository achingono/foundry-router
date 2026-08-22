"""Compatibility helpers re-exported by `foundry_router.main` for tests."""

from __future__ import annotations

import asyncio
import sys
from typing import Any

from foundry_router.api.common import api_error, finalize_non_streaming_credit
from foundry_router.forwarding import (
    BackendRequestResult,
    forward_non_streaming_with_retries,
    forward_streaming_with_retries,
    parse_retry_after,
    retry_delay_seconds,
    stream_response,
)
from foundry_router.routing import (
    execute_with_single_failover,
    ranked_model_backends,
    select_backend,
)


def _main() -> Any:
    return sys.modules["foundry_router.main"]


_parse_retry_after = parse_retry_after
_retry_delay_seconds = retry_delay_seconds
_select_backend = select_backend
_ranked_model_backends = ranked_model_backends


async def _forward_non_streaming_with_retries(**kwargs: Any) -> BackendRequestResult:
    return await forward_non_streaming_with_retries(
        **kwargs,
        get_backend_client=_main().get_backend_client,
        set_backend_active=_main()._set_backend_active,
        set_backend_cooldown=_main()._set_backend_cooldown,
        sleep=asyncio.sleep,
        api_error=api_error,
    )


async def _forward_streaming_with_retries(**kwargs: Any) -> BackendRequestResult:
    return await forward_streaming_with_retries(
        **kwargs,
        get_backend_client=_main().get_backend_client,
        set_backend_active=_main()._set_backend_active,
        set_backend_cooldown=_main()._set_backend_cooldown,
        sleep=asyncio.sleep,
        api_error=api_error,
        credit_store=_main()._credit_store,
        metrics_store=_main()._metrics_store,
        pre_output_timeout_seconds=_main().PRE_OUTPUT_TIMEOUT_SECONDS,
    )


async def _execute_with_single_failover(*args: Any, **kwargs: Any) -> Any:
    return await execute_with_single_failover(
        *args,
        **kwargs,
        health_store=_main()._health_store,
        credit_store=_main()._credit_store,
        metrics_store=_main()._metrics_store,
        logger=_main().logger,
        api_error=api_error,
        finalize_non_streaming_credit=lambda **inner: finalize_non_streaming_credit(
            **inner,
            credit_store=_main()._credit_store,
        ),
    )


def _stream_response(*args: Any, **kwargs: Any) -> Any:
    return stream_response(
        *args,
        **kwargs,
        set_backend_cooldown=_main()._set_backend_cooldown,
        credit_store=_main()._credit_store,
        metrics_store=_main()._metrics_store,
    )
