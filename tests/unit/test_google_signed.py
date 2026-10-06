"""Signed native Part fidelity and independent usage extraction before state failures."""

import base64
import time

import pytest

from foundry_router.api.adapters.google_signed import GoogleSignedAdapter
from foundry_router.api.google_continuation import prepare_continuation
from foundry_router.api.google_sealing import SealContext
from foundry_router.api.google_state import StateBinding, StateCodec, framed_digest
from foundry_router.config.google_features import GoogleFeatureProfile
from foundry_router.config.google_state import GoogleStateKeys

SCHEMA = {"type": "object", "properties": {}, "required": [], "additionalProperties": False}
BODY = {
    "model": "m",
    "foundry_provider_state": {"version": 1},
    "input": [{"role": "user", "content": "fixture"}],
    "tools": [{"type": "function", "name": "fixture", "strict": True, "parameters": SCHEMA}],
}


def adapter(prepared=None):
    profile = GoogleFeatureProfile(
        features=("function_tools",),
        continuation_policy="sealed_native",
        native_thinking_budget=0,
        thought_token_pricing=True,
        signature_input_token_bound=100000,
    )
    key = base64.urlsafe_b64encode(b"k" * 32)
    keys = GoogleStateKeys(
        scope_key=base64.urlsafe_b64encode(b"s" * 32).decode(),
        keys={"one": key.decode()},
        active="one",
        generation="fixture",
    )
    binding = StateBinding("caller", "m", "g", "fixture", "native", "v1", "config", "context")
    context = SealContext(
        StateCodec({"one": key}, active="one"),
        (("g", binding),),
        keys,
        prepared.request_digest if prepared else framed_digest("context", BODY),
    )
    return GoogleSignedAdapter(
        profile=profile, seal_context=context, backend_id="g", prepared=prepared
    )


def output(parts):
    return {
        "candidates": [{"content": {"role": "model", "parts": parts}, "finishReason": "STOP"}],
        "usageMetadata": {
            "promptTokenCount": 4,
            "candidatesTokenCount": 3,
            "thoughtsTokenCount": 2,
            "totalTokenCount": 9,
        },
    }


def test_signed_ordered_text_and_call_replay_preserves_each_part():
    first = adapter()
    provider = output(
        [
            {"text": "before", "thoughtSignature": "c2ln"},
            {"text": "adjacent", "thoughtSignature": "c2lnMg=="},
            {"functionCall": {"id": "call_fixture", "name": "fixture", "args": {}}},
        ]
    )
    result = first.translate_success("responses", provider, logical_model="m", request_body=BODY)
    assert result.input_tokens == 4 and result.output_tokens == 5
    assert len(result.body["output"]) == 3
    replay = {
        **BODY,
        "input": [
            *BODY["input"],
            *result.body["output"],
            {"type": "function_call_output", "call_id": "call_fixture", "output": "fixture"},
        ],
    }
    facts = prepare_continuation(
        replay, first.seal_context.codec, dict(first.seal_context.bindings), now=int(time.time())
    )
    second = adapter(facts)
    assert second.check_request("responses", replay) is None
    upstream = second.build_upstream_body(
        "responses", replay, deployment="fixture", default_output_tokens=10
    )
    assert upstream["contents"][1]["parts"] == provider["candidates"][0]["content"]["parts"]
    assert "foundry_provider_state" not in str(upstream)


@pytest.mark.parametrize(
    "part",
    [
        {"functionCall": {"id": "call_fixture", "name": "fixture", "args": {}}},
        {"text": "fixture", "thoughtSignature": "%%%"},
        {"text": "fixture", "thought": True, "thoughtSignature": "c2ln"},
    ],
)
def test_state_failures_retain_known_thought_usage(part):
    signed = adapter()
    provider = output([part])
    assert signed.extract_usage("responses", provider) == (4, 5)
    with pytest.raises(ValueError):
        signed.translate_success("responses", provider, logical_model="m", request_body=BODY)


def test_invalid_usage_not_normalized_into_success():
    provider = output([{"text": "fixture", "thoughtSignature": "c2ln"}])
    provider["usageMetadata"]["totalTokenCount"] = 99
    with pytest.raises(ValueError):
        adapter().translate_success("responses", provider, logical_model="m", request_body=BODY)


def test_signed_history_cannot_use_absent_owned_preparation():
    first = adapter()
    response = first.translate_success(
        "responses",
        output(
            [
                {
                    "functionCall": {"id": "call_fixture", "name": "fixture", "args": {}},
                    "thoughtSignature": "c2ln",
                }
            ]
        ),
        logical_model="m",
        request_body=BODY,
    )
    replay = {
        **BODY,
        "input": [
            *BODY["input"],
            *response.body["output"],
            {"type": "function_call_output", "call_id": "call_fixture", "output": "fixture"},
        ],
    }
    assert adapter().check_request("responses", replay).code == "invalid_provider_state"


def test_fresh_request_negotiation_is_required():
    assert (
        adapter()
        .check_request(
            "responses",
            {key: value for key, value in BODY.items() if key != "foundry_provider_state"},
        )
        .code
        == "invalid_provider_state"
    )


@pytest.mark.parametrize(
    "candidates",
    [
        [1],
        [{"content": None}],
        [{"content": 1}],
        [
            {
                "content": {"parts": [{"text": "fixture", "thoughtSignature": None}]},
                "finishReason": "STOP",
            }
        ],
        [
            {
                "content": {"parts": [{"text": "fixture", "thoughtSignature": ""}]},
                "finishReason": "STOP",
            }
        ],
    ],
)
def test_malformed_provider_shapes_and_explicit_null_signature_fail_safely(candidates):
    provider = {**output([]), "candidates": candidates}
    signed = adapter()
    assert signed.extract_usage("responses", provider) == (4, 5)
    with pytest.raises(ValueError):
        signed.translate_success("responses", provider, logical_model="m", request_body=BODY)


def test_prompt_block_preserves_refusal_without_replayable_state():
    provider = {
        "promptFeedback": {"blockReason": "SAFETY"},
        "usageMetadata": {"promptTokenCount": 4, "candidatesTokenCount": 0, "totalTokenCount": 4},
    }
    result = adapter().translate_success(
        "responses", provider, logical_model="m", request_body=BODY
    )
    assert all("foundry_provider_state" not in item for item in result.body["output"])
    assert result.body["status"] != "completed"


def test_whitespace_only_part_cannot_mint_unreplayable_turn():
    with pytest.raises(ValueError):
        adapter().translate_success(
            "responses",
            output([{"text": "   ", "thoughtSignature": "c2ln"}]),
            logical_model="m",
            request_body=BODY,
        )


def test_adjacent_separate_signed_turns_keep_native_content_boundaries():
    first = adapter()
    initial = first.translate_success(
        "responses",
        output([{"text": "first", "thoughtSignature": "c2ln"}]),
        logical_model="m",
        request_body=BODY,
    )
    replay = {**BODY, "input": [*BODY["input"], *initial.body["output"]]}
    facts = prepare_continuation(
        replay, first.seal_context.codec, dict(first.seal_context.bindings), now=int(time.time())
    )
    second = adapter(facts)
    final = second.translate_success(
        "responses",
        output([{"text": "second", "thoughtSignature": "c2lnMg=="}]),
        logical_model="m",
        request_body=replay,
    )
    replay["input"].extend(final.body["output"])
    facts = prepare_continuation(
        replay, first.seal_context.codec, dict(first.seal_context.bindings), now=int(time.time())
    )
    upstream = adapter(facts).build_upstream_body(
        "responses", replay, deployment="fixture", default_output_tokens=10
    )
    assert [part["parts"] for part in upstream["contents"] if part["role"] == "model"] == [
        [{"text": "first", "thoughtSignature": "c2ln"}],
        [{"text": "second", "thoughtSignature": "c2lnMg=="}],
    ]


def test_new_signature_cannot_exceed_retained_history_bound():
    first = adapter()
    response = first.translate_success(
        "responses",
        output([{"text": "fixture", "thoughtSignature": "c2ln"}]),
        logical_model="m",
        request_body=BODY,
    )
    replay = {**BODY, "input": [*BODY["input"], *response.body["output"]]}
    facts = prepare_continuation(
        replay, first.seal_context.codec, dict(first.seal_context.bindings), now=int(time.time())
    )
    signed = adapter(facts)
    signed.profile = signed.profile.model_copy(
        update={"signature_input_token_bound": facts.signature_input_tokens + 100}
    )
    with pytest.raises(ValueError):
        signed.translate_success(
            "responses",
            output([{"text": "next", "thoughtSignature": base64.b64encode(b"x" * 1000).decode()}]),
            logical_model="m",
            request_body=replay,
        )


def test_actual_sdk_signed_stream_final_state_and_replay():
    import json

    from openai import omit
    from openai._models import construct_type
    from openai.lib.streaming.responses._responses import ResponseStreamState
    from openai.types.responses import ResponseStreamEvent

    signed = adapter()
    decoder = signed.create_stream_decoder(logical_model="m", request_body=BODY)
    provider = output(
        [
            {
                "functionCall": {"id": "call_fixture", "name": "fixture", "args": {}},
                "thoughtSignature": "c2ln",
            }
        ]
    )
    wire = json.dumps(provider).encode()
    assert decoder.feed(wire[:50]) == decoder.feed(wire[50:]) == []
    state = ResponseStreamState(input_tools=omit, text_format=omit)
    for event in decoder.finish():
        state.handle_event(
            construct_type(type_=ResponseStreamEvent, value=json.loads(event.decode()[6:]))
        )
    completed = state._completed_response
    item = completed.output[0].model_dump(exclude_none=True)
    assert item["status"] == "completed" and "foundry_provider_state" in item
    replay = {
        **BODY,
        "input": [
            *BODY["input"],
            item,
            {"type": "function_call_output", "call_id": "call_fixture", "output": "fixture"},
        ],
    }
    assert (
        prepare_continuation(
            replay,
            signed.seal_context.codec,
            dict(signed.seal_context.bindings),
            now=int(time.time()),
        ).backend
        == "g"
    )
    assert decoder.usage == (4, 5) and not decoder.raw


def test_signed_stream_failed_seal_preserves_usage_and_emits_nothing():
    import json

    decoder = adapter().create_stream_decoder(logical_model="m", request_body=BODY)
    assert (
        decoder.feed(json.dumps(output([{"text": "fixture", "thoughtSignature": "%%%"}])).encode())
        == []
    )
    with pytest.raises(ValueError):
        decoder.finish()
    assert decoder.usage == (4, 5) and not decoder.meaningful_output and not decoder.raw


@pytest.mark.parametrize("refused", [False, True])
def test_signed_stream_text_refusal_sdk_terminal(refused):
    import json

    from openai import omit
    from openai._models import construct_type
    from openai.lib.streaming.responses._responses import ResponseStreamState
    from openai.types.responses import ResponseStreamEvent

    provider = (
        {
            "promptFeedback": {"blockReason": "SAFETY"},
            "usageMetadata": {
                "promptTokenCount": 4,
                "candidatesTokenCount": 0,
                "totalTokenCount": 4,
            },
        }
        if refused
        else output([{"text": "fixture", "thoughtSignature": "c2ln"}])
    )
    decoder = adapter().create_stream_decoder(logical_model="m", request_body=BODY)
    decoder.feed(json.dumps(provider).encode())
    state = ResponseStreamState(input_tools=omit, text_format=omit)
    events = decoder.finish()
    for event in events:
        state.handle_event(
            construct_type(type_=ResponseStreamEvent, value=json.loads(event.decode()[6:]))
        )
    if refused:
        terminal = json.loads(events[-1].decode()[6:])
        assert (
            terminal["type"] == "response.incomplete"
            and terminal["response"]["status"] == "incomplete"
        )
    else:
        assert state._completed_response.status == "completed"


def test_signed_stream_invalid_json_and_double_finish_are_safe():
    decoder = adapter().create_stream_decoder(logical_model="m", request_body=BODY)
    decoder.feed(b"invalid")
    with pytest.raises(ValueError):
        decoder.finish()
    with pytest.raises(ValueError):
        decoder.finish()
    with pytest.raises(ValueError):
        decoder.feed(b"late")


async def test_complete_native_json_prefetch_finishes_once_and_failure_is_safe():
    import json

    from foundry_router.forwarding import _prefetch_google_events

    decoder = adapter().create_stream_decoder(logical_model="m", request_body=BODY)

    async def chunks():
        yield json.dumps(output([{"text": "fixture", "thoughtSignature": "c2ln"}])).encode()

    events = []
    assert (
        await _prefetch_google_events(
            chunks(),
            decoder,
            events,
            deadline_monotonic=time.monotonic() + 5,
            pre_output_timeout_seconds=5,
        )
        is None
    )
    assert decoder.prefetch_finished and events and decoder.usage == (4, 5)
    failed = decoder.build_failure("SECRET-MARKER")
    assert b"SECRET-MARKER" not in b"".join(failed) and decoder.build_failure("again") == []


def test_success_terminal_delivery_prevents_second_failure():
    import json

    decoder = adapter().create_stream_decoder(logical_model="m", request_body=BODY)
    decoder.feed(json.dumps(output([{"text": "fixture", "thoughtSignature": "c2ln"}])).encode())
    events = decoder.finish()
    assert not decoder.terminal_sent
    for event in events:
        decoder.mark_delivered(event)
    assert decoder.terminal_sent and decoder.build_failure("late error") == []


@pytest.mark.parametrize(
    "field,value",
    [("instructions", "changed"), ("input", [{"role": "user", "content": "changed"}])],
)
def test_fresh_owned_snapshot_rejects_mutation_before_build_and_seal(field, value):
    signed = adapter()
    changed = {**BODY, field: value}
    assert signed.check_request("responses", changed).code == "invalid_provider_state"
    with pytest.raises(ValueError):
        signed.build_upstream_body(
            "responses", changed, deployment="fixture", default_output_tokens=10
        )
    with pytest.raises(ValueError):
        signed.translate_success(
            "responses", output([{"text": "fixture"}]), logical_model="m", request_body=changed
        )


@pytest.mark.parametrize("cancel", [False, True])
async def test_owned_finish_abandonment_never_publishes_late_worker_state(monkeypatch, cancel):
    import asyncio
    import json
    import threading

    signed = adapter()
    decoder = signed.create_stream_decoder(logical_model="m", request_body=BODY)
    decoder.feed(json.dumps(output([{"text": "fixture", "thoughtSignature": "c2ln"}])).encode())
    loop = asyncio.get_running_loop()
    entered = asyncio.Event()
    completed = asyncio.Event()
    release = threading.Event()
    original = signed.translate_success

    def delayed(*args, **kwargs):
        loop.call_soon_threadsafe(entered.set)
        try:
            assert release.wait(timeout=2)
            return original(*args, **kwargs)
        finally:
            loop.call_soon_threadsafe(completed.set)

    monkeypatch.setattr(signed, "translate_success", delayed)
    before = decoder.response_id
    task = asyncio.create_task(
        decoder.finish_owned(deadline=time.monotonic() + (2 if cancel else 0.1))
    )
    try:
        await asyncio.wait_for(entered.wait(), timeout=1)
        if cancel:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            with pytest.raises(ValueError):
                await task
        assert decoder.usage == (4, 5)
        failed = decoder.build_failure("private failure")
        snapshot = (decoder.sequence, decoder.event_bytes, decoder.terminal_sent)
        release.set()
        await asyncio.wait_for(completed.wait(), timeout=1)
        await asyncio.sleep(0)
        assert decoder.response_id == before
        assert (decoder.sequence, decoder.event_bytes, decoder.terminal_sent) == snapshot
        assert not decoder.meaningful_output
        assert b"response.failed" in failed[0]
        assert decoder.build_failure("again") == []
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)


async def test_owned_finish_success_publishes_exact_terminal_marker():
    import json

    decoder = adapter().create_stream_decoder(logical_model="m", request_body=BODY)
    decoder.feed(json.dumps(output([{"text": "fixture", "thoughtSignature": "c2ln"}])).encode())
    events = await decoder.finish_owned(deadline=time.monotonic() + 2)
    assert decoder.terminal_event is events[-1]
    decoder.mark_delivered(events[-1])
    assert decoder.terminal_sent and decoder.build_failure("again") == []


@pytest.mark.parametrize("after_terminal", [False, True])
async def test_signed_delivery_deadline_settles_once_and_preserves_terminal(after_terminal):
    import json
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from foundry_router.forwarding import _google_stream_response

    decoder = adapter().create_stream_decoder(logical_model="m", request_body=BODY)
    decoder.feed(json.dumps(output([{"text": "fixture", "thoughtSignature": "c2ln"}])).encode())
    events = await decoder.finish_owned(deadline=time.monotonic() + 2)
    decoder.prefetch_finished = True
    credit = AsyncMock()
    quota = AsyncMock()
    metrics = AsyncMock()
    context = AsyncMock()
    cooldown = AsyncMock()

    async def empty():
        if False:
            yield b""

    deadline = time.monotonic() + (2 if after_terminal else -1)
    stream = _google_stream_response(
        empty(),
        decoder,
        events,
        context,
        request_id="fixture",
        backend_id="g",
        cooldown_seconds=30,
        model="m",
        pricing={"m": SimpleNamespace(input_per_million=10, output_per_million=30)},
        status_code=200,
        set_backend_cooldown=cooldown,
        credit_store=credit,
        metrics_store=metrics,
        rate_limit_store=quota,
        deadline_monotonic=deadline,
        fallback_cost_usd=1,
        fallback_input_tokens=100000,
    )
    delivered = []
    if after_terminal:
        while not decoder.terminal_sent:
            delivered.append(await anext(stream))
        # Trigger the deadline at the next generator boundary without sleeping.
        with pytest.MonkeyPatch.context() as patches:
            patches.setattr(
                "foundry_router.forwarding._ensure_stream_deadline",
                lambda _: (_ for _ in ()).throw(TimeoutError()),
            )
            delivered.extend([event async for event in stream])
    else:
        delivered = [event async for event in stream]
    kinds = [json.loads(event.decode()[6:])["type"] for event in delivered]
    assert kinds.count("response.completed") == int(after_terminal)
    assert kinds.count("response.failed") == int(not after_terminal)
    credit.finalize_request.assert_awaited_once_with(
        "fixture", backend_id="g", charge_reserved=True, charged_cost_usd=pytest.approx(0.00019)
    )
    quota.finalize_request.assert_awaited_once_with("fixture", actual_input_tokens=4)
    context.__aexit__.assert_awaited_once()
    metrics.observe_request.assert_awaited_once()


@pytest.mark.parametrize("block_start", [False, True])
async def test_signed_asgi_blocked_send_enforces_deadline_and_closes(block_start):
    import asyncio
    import json
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from foundry_router.forwarding import DeadlineStreamingResponse, _google_stream_response

    decoder = adapter().create_stream_decoder(logical_model="m", request_body=BODY)
    decoder.feed(json.dumps(output([{"text": "fixture", "thoughtSignature": "c2ln"}])).encode())
    events = await decoder.finish_owned(deadline=time.monotonic() + 2)
    decoder.prefetch_finished = True
    credit, quota, metrics, context = (AsyncMock() for _ in range(4))
    fallback = AsyncMock()
    deadline = time.monotonic() + 0.05
    iterator = _google_stream_response(
        empty_chunks(),
        decoder,
        events,
        context,
        request_id="fixture",
        backend_id="g",
        cooldown_seconds=30,
        model="m",
        pricing={"m": SimpleNamespace(input_per_million=10, output_per_million=30)},
        status_code=200,
        set_backend_cooldown=AsyncMock(),
        credit_store=credit,
        metrics_store=metrics,
        rate_limit_store=quota,
        deadline_monotonic=deadline,
        fallback_cost_usd=1,
        fallback_input_tokens=100000,
    )
    response = DeadlineStreamingResponse(iterator, deadline=deadline, cleanup=fallback)
    seen = []

    async def send(message):
        seen.append(message["type"])
        if message["type"] == ("http.response.start" if block_start else "http.response.body"):
            await asyncio.Event().wait()

    with pytest.raises(TimeoutError):
        await response.stream_response(send)
    if block_start:
        fallback.assert_awaited_once()
        credit.finalize_request.assert_not_awaited()
    else:
        fallback.assert_not_awaited()
        credit.finalize_request.assert_awaited_once_with(
            "fixture", backend_id="g", charge_reserved=True, charged_cost_usd=pytest.approx(0.00019)
        )
        quota.finalize_request.assert_awaited_once_with("fixture", actual_input_tokens=4)
        context.__aexit__.assert_awaited_once()
    assert seen[0] == "http.response.start"


async def empty_chunks():
    if False:
        yield b""
