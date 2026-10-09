"""Actual Responses route over localhost proves early delivery and natural cancellation."""

import asyncio
import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/quality"))
import google_stream_runtime as runtime


def event(value):
    return b"data: " + json.dumps(value).encode() + b"\n\n"


class ProviderStream(httpx.AsyncByteStream):
    def __init__(self, *, cancel=False, overrun=False):
        self.cancel, self.overrun = cancel, overrun
        self.closed = False

    async def __aiter__(self):
        yield event(
            {
                "choices": [
                    {
                        "index": 0,
                        "delta": {"role": "assistant", "content": "ready"},
                        "finish_reason": None,
                    }
                ]
            }
        )
        await asyncio.sleep(10 if self.cancel else 0.1)
        yield event({"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]})
        yield event(
            {
                "choices": [],
                "usage": {
                    "prompt_tokens": 7,
                    "completion_tokens": 1025 if self.overrun else 2,
                    "total_tokens": 1032 if self.overrun else 9,
                },
            }
        )
        yield b"data: [DONE]\n\n"

    async def aclose(self):
        self.closed = True


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel", [False, True])
async def test_actual_route_incremental_complete_and_cancel(cancel):
    source = ProviderStream(cancel=cancel)
    calls, reserves, progress = [], [], []

    def provider(request):
        calls.append(request)
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, stream=source)

    result = await runtime.run_case(
        credential="synthetic-key",
        case={
            "case_id": "synthetic-stream",
            "project": "project-2",
            "stream": True,
            "cancel": cancel,
            "prompt": "cancel" if cancel else "ordinary",
        },
        transport=httpx.MockTransport(provider),
        reserve=lambda: reserves.append(True),
        progress=progress.append,
    )
    assert result["status"] == "passed", result
    assert result["natural_cleanup"] and result["public_text_before_upstream_eof"]
    assert result["settlement_matches"] and source.closed
    assert len(calls) == len(reserves) == 1
    if cancel:
        assert result["cancelled_before_upstream_eof"] and not result["terminal_usage"]
        assert result["actual_tokens"] is None
        assert result["settlement_kind"] == "conservative_reservation"
    else:
        assert result["terminal_usage"] and result["actual_tokens"] == 9
        assert any(item["actual_tokens"] == 9 for item in progress)


@pytest.mark.asyncio
async def test_output_overrun_persisted_before_failed_public_delivery():
    source = ProviderStream(overrun=True)
    progress = []
    result = await runtime.run_case(
        credential="synthetic-key",
        case={
            "case_id": "synthetic-overrun",
            "project": "project-2",
            "stream": True,
            "cancel": False,
            "prompt": "ordinary",
        },
        transport=httpx.MockTransport(lambda _: httpx.Response(200, stream=source)),
        reserve=lambda: None,
        progress=progress.append,
    )
    assert result["status"] == "failed" and result["budget_overrun"]
    assert any(item["budget_overrun"] and item["actual_tokens"] == 1032 for item in progress)
    assert source.closed and result["natural_cleanup"]


@pytest.mark.asyncio
async def test_nonstream_thought_inclusive_usage_matches_route_debit():
    progress = []
    payload = {
        "choices": [
            {"index": 0, "message": {"role": "assistant", "content": "93"}, "finish_reason": "stop"}
        ],
        "usage": {
            "prompt_tokens": 12,
            "completion_tokens": 20,
            "total_tokens": 32,
            "completion_tokens_details": {"reasoning_tokens": 10},
        },
    }
    result = await runtime.run_case(
        credential="synthetic-key",
        case={
            "case_id": "synthetic-reasoning",
            "project": "project-4",
            "stream": False,
            "cancel": False,
            "prompt": "reasoning",
        },
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload)),
        reserve=lambda: None,
        progress=progress.append,
    )
    assert result["status"] == "passed", result
    assert result["thought_tokens"] == 10 and result["actual_tokens"] == 32
    assert result["synthetic_debit_usd"] == 0.032 and result["terminal_usage"]


@pytest.mark.asyncio
async def test_header_persistence_failure_closes_received_response():
    source = ProviderStream()

    def progress(value):
        if value["provider_http_status"] is not None:
            raise OSError("synthetic disk failure")

    guard = runtime.IncrementalGuard(
        httpx.MockTransport(lambda _: httpx.Response(200, stream=source)),
        credential="synthetic-key",
        case={"stream": True, "prompt": "ordinary"},
        reserve=lambda: None,
        progress=progress,
    )
    request = httpx.Request(
        "POST",
        "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        headers={"authorization": "Bearer synthetic-key", "accept-encoding": "identity"},
        json={
            "model": runtime.MODEL,
            "messages": [{"role": "user", "content": runtime.PROMPTS["ordinary"]}],
            "max_completion_tokens": 1024,
            "stream": True,
            "stream_options": {"include_usage": True},
        },
    )
    try:
        with pytest.raises(OSError):
            await guard.handle_async_request(request)
        assert source.closed and guard.closed.is_set()
    finally:
        await guard.aclose()


@pytest.mark.parametrize(
    "tail",
    [
        event({"type": "response.failed"}),
        event({"type": "response.incomplete"}),
        event({"type": "error"}),
        event({"type": "response.completed", "response": {"status": "completed"}}),
        b"data: fragment",
    ],
)
def test_public_invalid_terminal_or_trailing_rejected(tail):
    public = runtime.PublicEvents()
    public.feed(event({"type": "response.completed", "response": {"status": "completed"}}))
    public.feed(tail)
    public.finish()
    assert public.invalid


def test_same_chunk_text_delta_then_failure_invalid_for_cancellation():
    public = runtime.PublicEvents()
    public.feed(
        event({"type": "response.output_text.delta", "delta": "ready"})
        + event({"type": "response.failed"})
    )
    assert public.first_text is not None and public.invalid


@pytest.mark.asyncio
@pytest.mark.parametrize("usage", [None, "private", []])
async def test_nonstream_invalid_usage_fails_safely(usage):
    result = await runtime.run_case(
        credential="synthetic-key",
        case={
            "case_id": "synthetic-badusage",
            "project": "project-4",
            "stream": False,
            "cancel": False,
            "prompt": "reasoning",
        },
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, json={"choices": None, "usage": usage})
        ),
        reserve=lambda: None,
        progress=lambda _: None,
    )
    assert result["status"] == "failed" and result["usage_invalid"]
    assert result["natural_cleanup"]


@pytest.mark.asyncio
async def test_stop_attached_usage_through_real_route_retains_terminal_facts():
    class StopAttached(ProviderStream):
        async def __aiter__(self):
            yield event(
                {
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"role": "assistant", "content": "ready"},
                            "finish_reason": None,
                        }
                    ]
                }
            )
            await asyncio.sleep(0.1)
            yield event(
                {
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 7, "completion_tokens": 2, "total_tokens": 9},
                }
            )
            yield b"data: [DONE]\n\n"

    source = StopAttached()
    progress = []
    result = await runtime.run_case(
        credential="synthetic-key",
        case={
            "case_id": "synthetic-stop",
            "project": "project-3",
            "stream": True,
            "cancel": False,
            "prompt": "reasoning",
        },
        terminal_facts=True,
        transport=httpx.MockTransport(lambda _: httpx.Response(200, stream=source)),
        reserve=lambda: None,
        progress=progress.append,
    )
    assert result["status"] == "passed", result
    assert result["terminal_usage"] and result["final_usage_shape"] == "stop_choice"
    assert all(result[key] for key in ("stop_seen", "done_seen", "upstream_eof"))
    assert any(value["final_usage_shape"] == "stop_choice" for value in progress)
