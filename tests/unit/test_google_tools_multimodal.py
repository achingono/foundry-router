"""Strict client, history, schema, stream and bounded media contracts."""

from __future__ import annotations

import base64
import copy
import io
import json
import struct
import time
import zlib

import pytest
from openai import omit
from openai._models import construct_type
from openai.lib.streaming.responses._responses import ResponseStreamState
from openai.types.responses import (
    ResponseFunctionCallArgumentsDeltaEvent,
    ResponseFunctionCallArgumentsDoneEvent,
    ResponseFunctionToolCall,
    ResponseStreamEvent,
)
from PIL import Image
from pydantic import ValidationError

from foundry_router.api.adapters.google_ai_studio import GoogleAiStudioAdapter
from foundry_router.api.adapters.google_media import validate_inline_image
from foundry_router.api.adapters.google_schema import (
    load_bounded_json,
    validate_schema,
    validate_value,
)
from foundry_router.api.adapters.google_tools import build_messages, request_context
from foundry_router.config import BackendConfig, PricingConfig, Settings
from foundry_router.config.google_features import GoogleFeatureProfile
from foundry_router.credit import estimate_request_cost

SCHEMA = {
    "type": "object",
    "properties": {"city": {"type": "string"}},
    "required": ["city"],
    "additionalProperties": False,
}
TOOL = {"type": "function", "name": "weather", "strict": True, "parameters": SCHEMA}


def profile(*features, **kw):
    features = features or ("function_tools",)
    return GoogleFeatureProfile(
        features=features,
        continuation_policy="unsigned" if "function_tools" in features else "disabled",
        **kw,
    )


def body(**kw):
    return {"model": "logical", "input": "hello", "tools": [copy.deepcopy(TOOL)], **kw}


def chat(*, text=None, calls=None, finish="tool_calls"):
    return {
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text, "tool_calls": calls or []},
                "finish_reason": finish,
            }
        ],
        "usage": {"prompt_tokens": 40, "completion_tokens": 10},
    }


def call(identity="c1", args='{"city":"Oslo"}', name="weather"):
    return {"id": identity, "type": "function", "function": {"name": name, "arguments": args}}


def chunk(delta=None, *, finish=None, usage=None):
    data = {"choices": [{"index": 0, "delta": delta or {}, "finish_reason": finish}]}
    if usage is not None:
        data = {"choices": [], "usage": usage}
    return f"data: {json.dumps(data)}\n\n".encode()


def events(raw):
    return [json.loads(event.decode().split("data: ", 1)[1]) for event in raw]


def png_uri(width=8, height=8, mode="RGB"):
    out = io.BytesIO()
    Image.new(mode, (width, height)).save(out, format="PNG")
    return "data:image/png;base64," + base64.b64encode(out.getvalue()).decode()


def test_profile_defaults_and_invalid_enablement():
    assert not GoogleFeatureProfile().features
    for kwargs in [
        {"features": ["function_tools"]},
        {"features": ["parallel_calls"]},
        {"features": ["inline_images"]},
        {"features": ["inline_pdf"]},
        {"features": ["function_tools"], "continuation_policy": "bound_history_required"},
        {"image_input_tokens": 1},
        {"max_image_pixels": 147457},
        {"combinations": [["json_object", "inline_images"]]},
    ]:
        with pytest.raises(ValidationError):
            GoogleFeatureProfile(**kwargs)
    with pytest.raises(ValidationError):
        BackendConfig(
            endpoint="https://example.test",
            credential="s",
            deployment="d",
            google_features=profile().model_dump(),
        )


def test_parallel_and_combination_gates():
    p = profile("function_tools", "json_schema")
    adapter = GoogleAiStudioAdapter(profile=p)
    request = body(
        text={"format": {"type": "json_schema", "name": "result", "strict": True, "schema": SCHEMA}}
    )
    assert adapter.check_request("responses", request)
    p = profile("function_tools", "json_schema", combinations=(("function_tools", "json_schema"),))
    assert GoogleAiStudioAdapter(profile=p).check_request("responses", request) is None
    assert adapter.check_request("responses", body(parallel_tool_calls=True))


def test_round_trip_pinned_client_preserves_ids_arguments_and_text():
    adapter = GoogleAiStudioAdapter(profile=profile())
    request = body()
    original = copy.deepcopy(request)
    translated = adapter.translate_success(
        "responses",
        chat(text="Checking.", calls=[call()]),
        logical_model="logical",
        request_body=request,
    ).body
    item = ResponseFunctionToolCall.model_validate(translated["output"][1]).model_dump(
        exclude_none=True
    )
    assert item["id"] != item["call_id"]
    assert item["call_id"] == "c1"
    history = [
        {"role": "user", "content": "hello"},
        *translated["output"],
        {
            "type": "function_call_output",
            "call_id": item["call_id"],
            "output": "local fixture result",
        },
    ]
    second = body(input=history)
    assert adapter.check_request("responses", second) is None
    upstream = adapter.build_upstream_body(
        "responses", second, deployment="provider-model", default_output_tokens=32
    )
    assert upstream["messages"][1]["tool_calls"][0] == call()
    assert upstream["messages"][1]["content"][0]["text"] == "Checking."
    assert upstream["messages"][2] == {
        "role": "tool",
        "tool_call_id": "c1",
        "content": "local fixture result",
    }
    assert request == original
    assert upstream["tools"][0]["function"]["strict"] is True


@pytest.mark.parametrize(
    "patch",
    [
        {"strict": None},
        {"strict": "true"},
        {"name": "../bad"},
        {"type": "web_search"},
        {"parameters": {"type": "object", "$ref": "https://secret.test"}},
    ],
)
def test_bad_declarations_fail_before_build(patch):
    request = body(tools=[{**TOOL, **patch}])
    adapter = GoogleAiStudioAdapter(profile=profile())
    assert adapter.check_request("responses", request)
    with pytest.raises(ValueError):
        adapter.build_upstream_body("responses", request, deployment="d", default_output_tokens=32)


@pytest.mark.parametrize(
    "history",
    [
        [{"type": "function_call_output", "call_id": "orphan", "output": "x"}],
        [
            {
                "type": "function_call",
                "call_id": "c1",
                "name": "weather",
                "arguments": '{"city":"x"}',
            }
        ],
        [{"type": "function_call", "call_id": "c1", "name": "other", "arguments": "{}"}],
        [
            {
                "type": "function_call",
                "call_id": "c1",
                "name": "weather",
                "arguments": '{"city":"x"}',
                "foundry_provider_state": "stripped",
            }
        ],
    ],
)
def test_invalid_history(history):
    assert GoogleAiStudioAdapter(profile=profile()).check_request("responses", body(input=history))


def test_parallel_history_requires_complete_results_and_unique_ids():
    adapter = GoogleAiStudioAdapter(
        profile=profile(
            "function_tools", "parallel_calls", combinations=(("function_tools", "parallel_calls"),)
        )
    )
    request = body()
    output = adapter.translate_success(
        "responses",
        chat(calls=[call("a"), call("b")]),
        logical_model="logical",
        request_body=request,
    ).body["output"]
    history = [
        *output,
        {"type": "function_call_output", "call_id": "b", "output": "b"},
        {"type": "function_call_output", "call_id": "a", "output": "a"},
    ]
    assert adapter.check_request("responses", body(input=history)) is None
    assert adapter.check_request("responses", body(input=history[:-1]))
    assert adapter.check_request("responses", body(input=[*history, history[-1]]))
    assert adapter.check_request("responses", body(input=[*history, output[0]]))


@pytest.mark.parametrize(
    "calls,choice",
    [
        ([call(args="{")], "auto"),
        ([call(args='{"city":1}')], "auto"),
        ([call(name="undeclared")], "auto"),
        ([call(), call()], "auto"),
        ([call()], "none"),
        ([], "required"),
    ],
)
def test_provider_tool_violations(calls, choice):
    adapter = GoogleAiStudioAdapter(profile=profile())
    with pytest.raises(ValueError):
        adapter.translate_success(
            "responses",
            chat(calls=calls, finish="stop"),
            logical_model="logical",
            request_body=body(tool_choice=choice),
        )


def test_signature_output_rejected_in_unsigned_profile():
    adapter = GoogleAiStudioAdapter(profile=profile())
    provider_call = {**call(), "extra_content": {"google": {"thought_signature": "PRIVATE"}}}
    with pytest.raises(ValueError):
        adapter.translate_success(
            "responses", chat(calls=[provider_call]), logical_model="logical", request_body=body()
        )


def test_bounded_schema_subset_and_json():
    validate_schema(SCHEMA, strict=True)
    validate_value({"city": "x"}, SCHEMA)
    for schema in [
        {**SCHEMA, "$defs": {}},
        {**SCHEMA, "anyOf": [SCHEMA]},
        {**SCHEMA, "additionalProperties": True},
        {**SCHEMA, "required": []},
        {**SCHEMA, "properties": {"city": {"type": "string", "pattern": ".*"}}},
        {**SCHEMA, "properties": {"city": {"type": "string", "enum": ["a"] * 129}}},
    ]:
        with pytest.raises(ValueError):
            validate_schema(schema, strict=True)
    for text in ['{"x":1,"x":2}', '{"x":NaN}', '{"x":1e999}', "[" * 33 + "0" + "]" * 33]:
        with pytest.raises(ValueError):
            load_bounded_json(text)
    for value in [{}, {"city": True}, {"city": "x", "extra": "y"}]:
        with pytest.raises(ValueError):
            validate_value(value, SCHEMA)


def test_structured_json_validation_and_incomplete_semantics():
    request = {
        "model": "logical",
        "input": "x",
        "text": {"format": {"type": "json_schema", "name": "s", "strict": True, "schema": SCHEMA}},
    }
    adapter = GoogleAiStudioAdapter(profile=profile("json_schema"))
    upstream = adapter.build_upstream_body(
        "responses", request, deployment="d", default_output_tokens=32
    )
    assert upstream["response_format"]["json_schema"]["schema"] == SCHEMA
    assert (
        adapter.translate_success(
            "responses",
            chat(text='{"city":"x"}', finish="stop"),
            logical_model="logical",
            request_body=request,
        ).body["status"]
        == "completed"
    )
    for text in ['{"city":1}', "{", '{"city":"x","extra":1}']:
        with pytest.raises(ValueError):
            adapter.translate_success(
                "responses",
                chat(text=text, finish="stop"),
                logical_model="logical",
                request_body=request,
            )
    assert (
        adapter.translate_success(
            "responses",
            chat(text="{", finish="length"),
            logical_model="logical",
            request_body=request,
        ).body["status"]
        == "incomplete"
    )


def test_stream_interleaved_fragmented_calls_and_late_usage():
    p = profile(
        "function_tools", "parallel_calls", combinations=(("function_tools", "parallel_calls"),)
    )
    decoder = GoogleAiStudioAdapter(profile=p).create_stream_decoder(
        logical_model="logical", request_body=body()
    )
    emitted = []
    emitted += decoder.feed(
        chunk(
            {
                "tool_calls": [
                    {"index": 0, "id": "ca", "function": {"name": "wea", "arguments": "{"}}
                ]
            }
        )
    )
    assert not emitted
    emitted += decoder.feed(
        chunk(
            {
                "tool_calls": [
                    {"index": 1, "id": "cb", "function": {"name": "weather", "arguments": "{"}},
                    {"index": 0, "id": "ll", "function": {"name": "ther"}},
                ]
            }
        )
    )
    emitted += decoder.feed(
        chunk(
            {
                "tool_calls": [
                    {"index": 0, "function": {"arguments": '"city":"x"}'}},
                    {"index": 1, "function": {"arguments": '"city":"y"}'}},
                ]
            }
        )
    )
    deltas = [
        event
        for event in events(emitted)
        if event["type"] == "response.function_call_arguments.delta"
    ]
    assert len(deltas) == 2
    for delta in deltas:
        ResponseFunctionCallArgumentsDeltaEvent.model_validate(delta)
    emitted += decoder.feed(chunk(finish="tool_calls"))
    assert not any(event["type"] == "response.completed" for event in events(emitted))
    emitted += decoder.feed(chunk(usage={"prompt_tokens": 70, "completion_tokens": 20}))
    emitted += decoder.feed(b"data: [DONE]\n\n")
    decoded = events(emitted)
    assert [event["sequence_number"] for event in decoded] == sorted(
        event["sequence_number"] for event in decoded
    )
    for event in decoded:
        if event["type"] == "response.function_call_arguments.done":
            ResponseFunctionCallArgumentsDoneEvent.model_validate(event)
    output = decoded[-1]["response"]["output"]
    calls = [
        ResponseFunctionToolCall.model_validate(item)
        for item in output
        if item["type"] == "function_call"
    ]
    assert [item.call_id for item in calls] == ["call", "cb"]
    assert decoded[-1]["response"]["usage"]["input_tokens"] == 70


def test_stream_invalid_completed_arguments_fail_with_usage():
    decoder = GoogleAiStudioAdapter(profile=profile()).create_stream_decoder(
        logical_model="logical", request_body=body()
    )
    decoder.feed(
        chunk(
            {
                "tool_calls": [
                    {"index": 0, "id": "c", "function": {"name": "weather", "arguments": "{"}}
                ]
            },
            finish="tool_calls",
        )
    )
    decoder.feed(chunk(usage={"prompt_tokens": 40, "completion_tokens": 10}))
    with pytest.raises(ValueError):
        decoder.feed(b"data: [DONE]\n\n")
    failure = events(decoder.build_failure("Backend returned an invalid stream"))[-1]
    assert failure["type"] == "response.failed"
    assert failure["response"]["usage"]["output_tokens"] == 10
    assert failure["response"]["output"][-1]["status"] == "incomplete"
    assert decoder.build_failure("again") == []


def test_media_mapping_order_bounds_and_estimate():
    p = profile("inline_images", image_input_tokens=258, image_token_pricing=True)
    uri = png_uri()
    image = {"type": "input_image", "image_url": uri}
    request = {
        "model": "logical",
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": "before"},
                    image,
                    {"type": "input_text", "text": "after"},
                ],
            }
        ],
    }
    adapter = GoogleAiStudioAdapter(profile=p)
    assert adapter.check_request("responses", request) is None
    upstream = adapter.build_upstream_body(
        "responses", request, deployment="d", default_output_tokens=32
    )
    parts = upstream["messages"][0]["content"]
    assert [part["type"] for part in parts] == ["text", "image_url", "text"]
    assert parts[1]["image_url"]["url"] == uri
    pricing = {
        "logical": PricingConfig(input_per_million=1, output_per_million=1, image_input_tokens=258)
    }
    estimate = estimate_request_cost(
        model="logical", operation="responses", body=request, pricing=pricing
    )
    assert estimate.input_tokens >= 258
    assert estimate.input_tokens < 600


@pytest.mark.parametrize(
    "uri",
    [
        "https://private.test/a.png",
        "file:/etc/passwd",
        "data:image/jpeg;base64,AAAA",
        "data:image/png;base64,%%%",
        "data:image/png;base64,AAAA",
    ],
)
def test_media_rejects_remote_malformed_and_mismatch(uri):
    p = profile("inline_images", image_input_tokens=258, image_token_pricing=True)
    with pytest.raises(ValueError):
        validate_inline_image({"type": "input_image", "image_url": uri}, p)


def test_media_pixels_ancillary_corruption_aggregate_and_deadline():
    p = profile("inline_images", image_input_tokens=258, image_token_pricing=True, max_images=1)
    for uri in [png_uri(385, 1), png_uri(mode="P"), png_uri(mode="L")]:
        with pytest.raises(ValueError):
            validate_inline_image({"type": "input_image", "image_url": uri}, p)
    raw = base64.b64decode(png_uri().split(",")[1])
    payload = b"zTXt" + b"x\x00\x00" + zlib.compress(b"BOMB" * 10000)
    extra = struct.pack(">I", len(payload) - 4) + payload + struct.pack(">I", zlib.crc32(payload))
    for modified in [raw[:33] + extra + raw[33:], raw + b"trailing", raw[:-1] + b"x"]:
        with pytest.raises(ValueError):
            validate_inline_image(
                {
                    "type": "input_image",
                    "image_url": "data:image/png;base64," + base64.b64encode(modified).decode(),
                },
                p,
            )
    request = {
        "input": [
            {"role": "user", "content": [{"type": "input_image", "image_url": png_uri()}] * 2}
        ]
    }
    assert GoogleAiStudioAdapter(profile=p).check_request("responses", request)
    with pytest.raises(ValueError):
        build_messages(
            {"input": [{"role": "user", "content": "x"}]},
            p,
            request_context({}, p),
            deadline=time.monotonic() - 1,
        )


def test_tool_estimates_include_keys_schemas_and_results():
    pricing = {"logical": PricingConfig(input_per_million=1, output_per_million=1)}
    plain = estimate_request_cost(
        model="logical", operation="responses", body={"input": "hello"}, pricing=pricing
    )
    tool = estimate_request_cost(
        model="logical", operation="responses", body=body(), pricing=pricing
    )
    assert tool.input_tokens > plain.input_tokens + len(json.dumps(SCHEMA))


def test_pool_uses_maximum_server_owned_image_bound():
    backends = {}
    for name, bound in [("a", 258), ("b", 600)]:
        backends[name] = {
            "provider": "google_ai_studio",
            "endpoint": "https://provider.test",
            "credential": "synthetic",
            "deployment": "d",
            "credit_metered": False,
            "google_features": profile(
                "inline_images", image_input_tokens=bound, image_token_pricing=True
            ).model_dump(),
        }
    settings = Settings(
        backends_json=json.dumps(backends),
        models_json='{"logical":{"backends":{"a":1,"b":1}}}',
        client_api_keys_json='["synthetic-client"]',
        admin_api_keys_json='["synthetic-admin"]',
    )
    assert settings.pricing["logical"].image_input_tokens == 600


def consume_sdk(raw):
    state = ResponseStreamState(input_tools=omit, text_format=omit)
    for event in events(raw):
        state.handle_event(construct_type(type_=ResponseStreamEvent, value=event))
    return state


def test_sdk_out_of_order_ready_calls_and_call_first_text_replay():
    p = profile(
        "function_tools", "parallel_calls", combinations=(("function_tools", "parallel_calls"),)
    )
    adapter = GoogleAiStudioAdapter(profile=p)
    request = body()
    decoder = adapter.create_stream_decoder(logical_model="logical", request_body=request)
    raw = []
    raw += decoder.feed(
        chunk(
            {
                "tool_calls": [
                    {"index": 1, "id": "b", "function": {"name": "weather", "arguments": "{"}}
                ]
            }
        )
    )
    raw += decoder.feed(
        chunk({"tool_calls": [{"index": 1, "function": {"arguments": '"city":"b"}'}}]})
    )
    raw += decoder.feed(chunk({"content": "checking"}))
    raw += decoder.feed(
        chunk(
            {
                "tool_calls": [
                    {
                        "index": 0,
                        "id": "a",
                        "function": {"name": "weather", "arguments": '{"city":"a"}'},
                    }
                ]
            },
            finish="tool_calls",
        )
    )
    raw += decoder.feed(b"data: [DONE]\n\n")
    consume_sdk(raw)
    output = events(raw)[-1]["response"]["output"]
    assert [item["type"] for item in output] == ["function_call", "message", "function_call"]
    history = [
        *output,
        {"type": "function_call_output", "call_id": "a", "output": "a"},
        {"type": "function_call_output", "call_id": "b", "output": "b"},
    ]
    assert adapter.check_request("responses", body(input=history)) is None


def test_sdk_tool_only_stream_has_no_empty_message_and_replays():
    adapter = GoogleAiStudioAdapter(profile=profile())
    decoder = adapter.create_stream_decoder(logical_model="logical", request_body=body())
    raw = decoder.feed(
        chunk(
            {
                "tool_calls": [
                    {
                        "index": 0,
                        "id": "c",
                        "function": {"name": "weather", "arguments": '{"city":"x"}'},
                    }
                ]
            },
            finish="tool_calls",
        )
    )
    raw += decoder.feed(b"data: [DONE]\n\n")
    consume_sdk(raw)
    output = events(raw)[-1]["response"]["output"]
    assert len(output) == 1
    assert (
        adapter.check_request(
            "responses",
            body(input=[*output, {"type": "function_call_output", "call_id": "c", "output": "x"}]),
        )
        is None
    )


@pytest.mark.parametrize(
    "content",
    [
        [{"type": "text", "text": "x", "thought_signature": "PRIVATE"}],
        [{"type": "other", "text": "x"}],
    ],
)
def test_signed_or_unknown_text_parts_rejected_in_both_modes(content):
    adapter = GoogleAiStudioAdapter()
    with pytest.raises(ValueError):
        adapter.translate_success("responses", chat(text=content, finish="stop"), logical_model="m")
    with pytest.raises(ValueError):
        adapter.create_stream_decoder(logical_model="m").feed(chunk({"content": content}))


def test_named_choice_exactly_one_malformed_names_and_historical_id_reuse():
    p = profile(
        "function_tools", "parallel_calls", combinations=(("function_tools", "parallel_calls"),)
    )
    adapter = GoogleAiStudioAdapter(profile=p)
    for calls in [[call("a"), call("b")], [call(name=[])], [call(name={})]]:
        with pytest.raises(ValueError):
            adapter.translate_success(
                "responses",
                chat(calls=calls),
                logical_model="m",
                request_body=body(tool_choice={"type": "function", "name": "weather"}),
            )
    history = [
        {"type": "function_call", "call_id": "a", "name": "weather", "arguments": '{"city":"x"}'},
        {"type": "function_call_output", "call_id": "a", "output": "x"},
    ]
    with pytest.raises(ValueError):
        adapter.translate_success(
            "responses",
            chat(calls=[call("a")]),
            logical_model="m",
            request_body=body(input=history),
        )


def test_historical_parallel_calls_require_combination_even_with_future_serial():
    p = profile("function_tools", "parallel_calls")
    history = [
        {"type": "function_call", "call_id": name, "name": "weather", "arguments": '{"city":"x"}'}
        for name in ["a", "b"]
    ]
    history += [
        {"type": "function_call_output", "call_id": name, "output": "x"} for name in ["a", "b"]
    ]
    assert GoogleAiStudioAdapter(profile=p).check_request(
        "responses", body(input=history, parallel_tool_calls=False)
    )


def test_required_tool_refusal_nonstream_and_stream_sdk():
    adapter = GoogleAiStudioAdapter(profile=profile())
    request = body(tool_choice="required")
    upstream = chat(finish="stop")
    upstream["choices"][0]["message"]["refusal"] = "cannot do that"
    result = adapter.translate_success(
        "responses", upstream, logical_model="m", request_body=request
    )
    assert result.body["output"][0]["content"][0]["type"] == "refusal"
    decoder = adapter.create_stream_decoder(logical_model="m", request_body=request)
    raw = decoder.feed(chunk({"refusal": "cannot "}))
    raw += decoder.feed(chunk({"refusal": "do that"}, finish="stop"))
    raw += decoder.feed(b"data: [DONE]\n\n")
    consume_sdk(raw)
    assert events(raw)[-1]["response"]["output"][0]["content"][0] == {
        "type": "refusal",
        "refusal": "cannot do that",
    }


def test_azure_image_legacy_estimate_and_feature_instruction_byte_ceiling():
    pricing = {"logical": PricingConfig(input_per_million=1, output_per_million=1)}
    azure = {
        "input": [
            {
                "role": "user",
                "content": [{"type": "input_image", "image_url": "https://azure.example.test/x"}],
            }
        ]
    }
    assert (
        estimate_request_cost(model="logical", operation="responses", body=azure, pricing=pricing)
        is not None
    )
    instructions = "界" * 2000
    estimate = estimate_request_cost(
        model="logical",
        operation="responses",
        body=body(instructions=instructions),
        pricing=pricing,
    )
    assert estimate.input_tokens >= len(instructions.encode())


def test_image_count_rejected_before_extra_decode(monkeypatch):
    import foundry_router.api.adapters.google_tools as helper

    p = profile("inline_images", image_input_tokens=258, image_token_pricing=True, max_images=1)
    calls = []
    monkeypatch.setattr(
        helper, "validate_inline_image", lambda part, _profile, **_kwargs: calls.append(part) or 50
    )
    image = {"type": "input_image", "image_url": png_uri()}
    assert GoogleAiStudioAdapter(profile=p).check_request(
        "responses", {"input": [{"role": "user", "content": [image] * 64}]}
    )
    assert len(calls) == 1


def test_same_chunk_invalid_output_retains_valid_usage():
    decoder = GoogleAiStudioAdapter(profile=profile()).create_stream_decoder(
        logical_model="m", request_body=body()
    )
    payload = {
        "choices": [
            {
                "delta": {
                    "tool_calls": [
                        {"index": 0, "id": "c", "function": {"name": "weather", "arguments": []}}
                    ]
                }
            }
        ],
        "usage": {"prompt_tokens": 17, "completion_tokens": 8},
    }
    with pytest.raises(ValueError):
        decoder.feed(f"data: {json.dumps(payload)}\n\n".encode())
    assert decoder.usage == (17, 8)


def test_image_only_uses_conservative_text_and_instruction_ceiling():
    instructions = "界" * 1000
    text = "界" * 1000
    pricing = {
        "logical": PricingConfig(input_per_million=0, output_per_million=0, image_input_tokens=258)
    }
    request = {
        "instructions": instructions,
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": text},
                    {"type": "input_image", "image_url": png_uri()},
                ],
            }
        ],
    }
    estimate = estimate_request_cost(
        model="logical", operation="responses", body=request, pricing=pricing
    )
    assert estimate.input_tokens >= len(instructions.encode()) + len(text.encode()) + 258


def test_mixed_provider_image_pool_rejected():
    p = profile("inline_images", image_input_tokens=258, image_token_pricing=True)
    backends = {
        "g": {
            "provider": "google_ai_studio",
            "endpoint": "https://provider.test",
            "credential": "s",
            "deployment": "d",
            "google_features": p.model_dump(),
        },
        "a": {"endpoint": "https://azure.test", "credential": "s", "deployment": "d"},
    }
    with pytest.raises(ValidationError, match="Google-only"):
        Settings(
            backends_json=json.dumps(backends),
            models_json='{"m":{"backends":{"g":1,"a":1}}}',
            client_api_keys_json='["c"]',
            admin_api_keys_json='["a"]',
        )


def test_intake_timeout_documented_environment_variable(monkeypatch):
    monkeypatch.setenv("FOUNDRY_INTAKE_TIMEOUT_SECONDS", "12.5")
    settings = Settings(
        backends_json='{"g":{"endpoint":"https://synthetic.test","credential":"s","deployment":"d","credit_metered":false}}',
        models_json='{"m":{"backends":{"g":1}}}',
        client_api_keys_json='["c"]',
        admin_api_keys_json='["a"]',
    )
    assert settings.intake_timeout_seconds == 12.5
