"""Explicit native surface, stateless histories, usage and SSE client gates."""

from __future__ import annotations

import json

import pytest
from openai import omit
from openai._models import construct_type
from openai.lib.streaming.responses._responses import ResponseStreamState
from openai.types.responses import ResponseStreamEvent
from pydantic import ValidationError

from foundry_router.api.adapters import get_adapter
from foundry_router.api.adapters.google_native import GoogleNativeAdapter, native_usage
from foundry_router.config import BackendConfig
from foundry_router.config.google_features import GoogleFeatureProfile

SCHEMA = {
    "type": "object",
    "properties": {"x": {"type": "integer"}},
    "required": ["x"],
    "additionalProperties": False,
}
TOOL = {"type": "function", "name": "f", "strict": True, "parameters": SCHEMA}


def profile(*features):
    return GoogleFeatureProfile(
        features=features,
        combinations=(features,) if len(features) > 1 else (),
        continuation_policy="unsigned" if "function_tools" in features else "disabled",
        native_thinking_disabled=True,
    )


def response(parts=None, *, finish="STOP", usage=None):
    result = {
        "candidates": [
            {"index": 0, "content": {"role": "model", "parts": parts or []}, "finishReason": finish}
        ]
    }
    if usage is not None:
        result["usageMetadata"] = usage
    return result


def stream(data):
    return f"data: {json.dumps(data)}\n\n".encode()


def test_native_configuration_gate_and_factory():
    args = {
        "provider": "google_ai_studio",
        "api_surface": "native",
        "endpoint": "https://native.example.test",
        "credential": "synthetic",
        "deployment": "test-model",
        "google_features": {"native_thinking_disabled": True},
    }
    backend = BackendConfig(**args)
    assert backend.supported_operations == ["responses"]
    assert isinstance(
        get_adapter(
            backend.provider,
            api_surface=backend.api_surface,
            google_features=backend.google_features,
        ),
        GoogleNativeAdapter,
    )
    for patch in (
        {"google_features": {}},
        {"provider": "azure_foundry"},
        {"supported_operations": ["responses", "embeddings"]},
        {"endpoint": "https://native.example.test/v1beta/openai"},
    ):
        with pytest.raises(ValidationError):
            BackendConfig(**{**args, **patch})


def test_native_request_system_order_schema_choice_and_grouped_parallel_results():
    adapter = GoogleNativeAdapter(
        profile=profile("function_tools", "parallel_calls", "json_schema")
    )
    calls = [
        {"type": "function_call", "call_id": f"c{i}", "name": "f", "arguments": '{"x":1}'}
        for i in (1, 2)
    ]
    body = {
        "model": "logical",
        "instructions": "first",
        "tools": [TOOL],
        "text": {"format": {"type": "json_schema", "name": "s", "schema": SCHEMA, "strict": True}},
        "input": [
            {"role": "system", "content": "second"},
            {"role": "user", "content": "question"},
            {"role": "assistant", "content": "calls"},
            *calls,
            *[
                {"type": "function_call_output", "call_id": f"c{i}", "output": f"result{i}"}
                for i in (1, 2)
            ],
            {"role": "user", "content": "continue"},
        ],
    }
    assert adapter.check_request("responses", body) is None
    upstream = adapter.build_upstream_body(
        "responses", body, deployment="ignored", default_output_tokens=100
    )
    assert "model" not in upstream and "stream" not in upstream
    assert upstream["systemInstruction"]["parts"] == [{"text": "first"}, {"text": "second"}]
    assert [item["role"] for item in upstream["contents"]] == ["user", "model", "user"]
    results = upstream["contents"][-1]["parts"]
    assert [part["functionResponse"]["id"] for part in results[:-1]] == ["c1", "c2"]
    assert results[-1] == {"text": "continue"}
    assert upstream["generationConfig"]["responseJsonSchema"] == SCHEMA
    assert upstream["generationConfig"]["thinkingConfig"] == {"thinkingBudget": 0}
    body["input"].append({"role": "system", "content": "late"})
    assert adapter.check_request("responses", body) is not None


@pytest.mark.parametrize(
    "choice,mode",
    [
        ("auto", "AUTO"),
        ("none", "NONE"),
        ("required", "ANY"),
        ({"type": "function", "name": "f"}, "ANY"),
    ],
)
def test_native_tool_choice(choice, mode):
    adapter = GoogleNativeAdapter(profile=profile("function_tools"))
    upstream = adapter.build_upstream_body(
        "responses",
        {"input": "x", "tools": [TOOL], "tool_choice": choice},
        deployment="unused",
        default_output_tokens=100,
    )
    assert upstream["toolConfig"]["functionCallingConfig"]["mode"] == mode
    assert upstream["tools"][0]["functionDeclarations"][0]["parametersJsonSchema"] == SCHEMA


def test_native_usage_totals_cache_thoughts_and_failure_retention():
    usage = {
        "promptTokenCount": 30,
        "candidatesTokenCount": 5,
        "thoughtsTokenCount": 2,
        "totalTokenCount": 37,
        "cachedContentTokenCount": 10,
    }
    assert native_usage({"usageMetadata": usage}) == (30, 7)
    with pytest.raises(ValueError, match="disabled"):
        native_usage({"usageMetadata": usage}, strict=True)
    for patch in (
        {"totalTokenCount": 35},
        {"cachedContentTokenCount": 31},
        {"promptTokenCount": True},
        {"candidatesTokenCount": -1},
    ):
        assert native_usage({"usageMetadata": {**usage, **patch}}) == (None, None)
        with pytest.raises(ValueError):
            native_usage({"usageMetadata": {**usage, **patch}}, strict=True)
    assert native_usage({}) == (None, None)


def test_native_nonstream_tools_json_refusal_and_opaque_state():
    adapter = GoogleNativeAdapter(profile=profile("function_tools"))
    body = {"input": "x", "tools": [TOOL]}
    raw = response([{"functionCall": {"id": "c1", "name": "f", "args": {"x": 1}}}])
    result = adapter.translate_success("responses", raw, logical_model="logical", request_body=body)
    assert result.body["output"][0]["call_id"] == "c1"
    for part in (
        {"text": "secret", "thoughtSignature": "secret"},
        {"thought": True, "text": "secret"},
        {"inlineData": {"mimeType": "image/png", "data": "secret"}},
        {"functionCall": {"name": "f", "args": {"x": 1}}},
    ):
        with pytest.raises(ValueError):
            adapter.translate_success(
                "responses", response([part]), logical_model="logical", request_body=body
            )
    blocked = adapter.translate_success(
        "responses",
        {"promptFeedback": {"blockReason": "SAFETY"}},
        logical_model="logical",
        request_body=body,
    )
    assert blocked.body["status"] == "incomplete"
    assert blocked.body["output"][0]["content"][0]["type"] == "refusal"


def test_native_stream_actual_client_cumulative_usage_clean_eof():
    adapter = GoogleNativeAdapter(profile=profile("function_tools"))
    body = {"input": "x", "tools": [TOOL]}
    decoder = adapter.create_stream_decoder(logical_model="logical", request_body=body)
    raw = []
    raw.extend(decoder.feed(stream(response([{"text": "before"}], finish=None))))
    raw.extend(
        decoder.feed(
            stream(
                response(
                    [{"functionCall": {"id": "c1", "name": "f", "args": {"x": 1}}}], finish="STOP"
                )
            )
        )
    )
    raw.extend(
        decoder.feed(
            stream(
                {
                    "usageMetadata": {
                        "promptTokenCount": 30,
                        "candidatesTokenCount": 5,
                        "totalTokenCount": 35,
                    }
                }
            )
        )
    )
    assert not any(b"response.completed" in event for event in raw)
    raw.extend(decoder.finish())
    state = ResponseStreamState(text_format=omit, input_tools=omit)
    for event in raw:
        payload = json.loads(event.decode().split("data: ", 1)[1])
        state.handle_event(construct_type(type_=ResponseStreamEvent, value=payload))
    result = state._completed_response
    assert result.status == "completed" and result.usage.total_tokens == 35
    assert [item.type for item in result.output] == ["message", "function_call"]
    assert decoder.usage == (30, 5)


@pytest.mark.parametrize("fault", ["partial", "no_finish", "after_finish", "decreasing", "state"])
def test_native_stream_failure_preserves_usage_and_never_completes(fault):
    decoder = GoogleNativeAdapter(profile=profile()).create_stream_decoder(logical_model="m")
    decoder.feed(
        stream(
            response(
                [{"text": "x"}],
                finish="STOP" if fault != "no_finish" else None,
                usage={"promptTokenCount": 10, "candidatesTokenCount": 2},
            )
        )
    )
    with pytest.raises(ValueError):
        if fault == "partial":
            decoder.feed(b"data: {")
            decoder.finish()
        elif fault == "no_finish":
            decoder.finish()
        elif fault == "after_finish":
            decoder.feed(stream(response([{"text": "late"}], finish=None)))
        elif fault == "decreasing":
            decoder.feed(
                stream({"usageMetadata": {"promptTokenCount": 9, "candidatesTokenCount": 2}})
            )
        else:
            decoder.feed(
                stream(
                    response(
                        [{"text": "private", "thoughtSignature": "private"}],
                        usage={"promptTokenCount": 10, "candidatesTokenCount": 3},
                    )
                )
            )
    if fault == "decreasing":
        assert decoder.usage_invalid and decoder.usage == (None, None)
    else:
        assert decoder.usage[0] == 10


@pytest.mark.parametrize("streamed", [False, True])
def test_native_interleaved_parts_actual_client_round_trip(streamed):
    adapter = GoogleNativeAdapter(profile=profile("function_tools", "parallel_calls"))
    body = {"input": [{"role": "user", "content": "x"}], "tools": [TOOL]}
    parts = [
        {"functionCall": {"id": "c1", "name": "f", "args": {"x": 1}}},
        {"text": "between"},
        {"functionCall": {"id": "c2", "name": "f", "args": {"x": 2}}},
        {"text": "after"},
    ]
    if streamed:
        decoder = adapter.create_stream_decoder(logical_model="m", request_body=body)
        events = decoder.feed(stream(response(parts))) + decoder.finish()
        state = ResponseStreamState(text_format=omit, input_tools=omit)
        for event in events:
            payload = json.loads(event.decode().split("data: ", 1)[1])
            state.handle_event(construct_type(type_=ResponseStreamEvent, value=payload))
        result = state._completed_response
        completed_items = {
            json.loads(event.decode().split("data: ", 1)[1])["item"]["id"]: json.loads(
                event.decode().split("data: ", 1)[1]
            )["item"]
            for event in events
            if b'"type":"response.output_item.done"' in event
        }
        assert [completed_items[item.id]["status"] for item in result.output] == [
            "completed"
        ] * len(result.output)
        output = [item.model_dump(exclude_none=True) for item in result.output]
        assert result.status == "completed"
    else:
        output = adapter.translate_success(
            "responses", response(parts), logical_model="m", request_body=body
        ).body["output"]
    assert [item["type"] for item in output] == [
        "function_call",
        "message",
        "function_call",
        "message",
    ]
    body["input"].extend(output)
    body["input"].extend(
        [{"type": "function_call_output", "call_id": f"c{i}", "output": "ok"} for i in (1, 2)]
    )
    assert adapter.check_request("responses", body) is None
    replay = adapter.build_upstream_body(
        "responses", body, deployment="unused", default_output_tokens=100
    )
    assert replay["contents"][1]["parts"] == parts


@pytest.mark.parametrize("boundary", ["envelope", "candidate", "content", "feedback", "usage_only"])
def test_native_unknown_state_rejected_at_each_boundary(boundary):
    raw = response([{"text": "x"}])
    target = raw
    if boundary == "candidate":
        target = raw["candidates"][0]
    elif boundary == "content":
        target = raw["candidates"][0]["content"]
    elif boundary == "feedback":
        raw = {"promptFeedback": {"blockReason": "SAFETY"}}
        target = raw["promptFeedback"]
    elif boundary == "usage_only":
        raw = {"usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 2}}
        target = raw
    target["privateState"] = "PRIVATE_STATE"
    adapter = GoogleNativeAdapter(profile=profile())
    with pytest.raises(ValueError):
        adapter.translate_success("responses", raw, logical_model="m")
    with pytest.raises(ValueError):
        adapter.create_stream_decoder(logical_model="m").feed(stream(raw))


@pytest.mark.parametrize("malformed", [[], {}, True, 1])
def test_native_finish_and_block_enum_shapes_fail_safely(malformed):
    adapter = GoogleNativeAdapter(profile=profile())
    for raw in (
        response([{"text": "x"}], finish=malformed),
        {"promptFeedback": {"blockReason": malformed}},
    ):
        with pytest.raises(ValueError):
            adapter.translate_success("responses", raw, logical_model="m")
        with pytest.raises(ValueError):
            adapter.create_stream_decoder(logical_model="m").feed(stream(raw))


def test_native_nonstream_aggregate_text_bound():
    adapter = GoogleNativeAdapter(profile=profile())
    with pytest.raises(ValueError, match="aggregate"):
        adapter.translate_success(
            "responses", response([{"text": "x" * 65537}] * 64), logical_model="m"
        )


@pytest.mark.parametrize(
    "patch", [{"totalTokenCount": 99}, {"promptTokenCount": -1}, {"candidatesTokenCount": True}]
)
def test_native_invalid_final_usage_clears_earlier_dimensions(patch):
    decoder = GoogleNativeAdapter(profile=profile()).create_stream_decoder(logical_model="m")
    decoder.feed(
        stream(response([{"text": "x"}], usage={"promptTokenCount": 10, "candidatesTokenCount": 2}))
    )
    with pytest.raises(ValueError):
        decoder.feed(
            stream({"usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 3, **patch}})
        )
    assert decoder.usage_invalid and decoder.usage == (None, None)


def test_native_explicit_null_usage_and_empty_candidates_fail_closed():
    adapter = GoogleNativeAdapter(profile=profile())
    for raw in (
        {"usageMetadata": None},
        {"candidates": [], "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 2}},
    ):
        with pytest.raises(ValueError):
            adapter.create_stream_decoder(logical_model="m").feed(stream(raw))


@pytest.mark.parametrize("finish", ["MAX_TOKENS", "STOP"])
def test_native_archived_message_final_status_matches_done_event(finish):
    adapter = GoogleNativeAdapter(profile=profile("function_tools", "json_schema"))
    body = {
        "input": "x",
        "tools": [TOOL],
        "text": {"format": {"type": "json_schema", "name": "s", "strict": True, "schema": SCHEMA}},
    }
    decoder = adapter.create_stream_decoder(logical_model="m", request_body=body)
    events = decoder.feed(
        stream(
            response(
                [
                    {"text": "invalid json"},
                    {"functionCall": {"id": "c1", "name": "f", "args": {"x": 1}}},
                ],
                finish=finish,
            )
        )
    )
    assert not any(b'"type":"response.output_item.done"' in event for event in events)
    if finish == "STOP":
        with pytest.raises(ValueError):
            decoder.finish()
        terminal = json.loads(decoder.build_failure("safe")[0].decode().split("data: ", 1)[1])[
            "response"
        ]
        assert all(item["status"] == "incomplete" for item in terminal["output"])
    else:
        events.extend(decoder.finish())
        decoded = [json.loads(event.decode().split("data: ", 1)[1]) for event in events]
        terminal = decoded[-1]["response"]
        done = {
            event["item"]["id"]: event["item"]
            for event in decoded
            if event["type"] == "response.output_item.done"
        }
        assert terminal["status"] == "incomplete"
        assert all(
            done[item["id"]]["status"] == item["status"] == "incomplete"
            for item in terminal["output"]
        )
