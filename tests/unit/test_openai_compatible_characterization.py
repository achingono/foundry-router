"""Immutable wire fixtures captured from the Google adapter before extraction.

The JSON oracle was captured at deb05a5; never regenerate it from extracted code.
All requests, provider outputs and cryptographic material are synthetic.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pytest

from foundry_router.api.adapters.google_ai_studio import GoogleAiStudioAdapter
from foundry_router.api.adapters.google_native import GoogleNativeAdapter
from foundry_router.config.google_features import GoogleFeatureProfile
from tests.unit.test_google_audio_output import BODY as AUDIO_BODY
from tests.unit.test_google_audio_output import adapter as audio_adapter
from tests.unit.test_google_audio_output import media, native
from tests.unit.test_google_signed import BODY as SIGNED_BODY
from tests.unit.test_google_signed import adapter as signed_adapter
from tests.unit.test_google_signed import output as signed_output

ORACLE = Path(__file__).parents[1] / "fixtures" / "openai_compatible_characterization.json"
SCHEMA = {
    "type": "object",
    "properties": {"x": {"type": "integer"}},
    "required": ["x"],
    "additionalProperties": False,
}
TOOL = {"type": "function", "name": "f", "strict": True, "parameters": SCHEMA}
CASES = (
    "rejections",
    "requests",
    "text",
    "parallel_calls",
    "structured",
    "refusal",
    "length",
    "content_filter",
    "missing_usage",
    "errors",
    "stream_text",
    "stream_parallel",
    "stream_structured",
    "stream_refusal",
    "stream_length",
    "stream_missing_usage",
    "stream_failure",
    "embeddings",
    "native_ordered",
    "signed_ordered",
    "audio_lifecycle",
)


def _profile() -> GoogleFeatureProfile:
    features = ("function_tools", "parallel_calls", "json_schema")
    return GoogleFeatureProfile(
        features=features,
        combinations=(features, ("function_tools", "parallel_calls")),
        continuation_policy="unsigned",
        native_thinking_disabled=True,
    )


def _chat(message: dict[str, Any], finish: str = "stop") -> dict[str, Any]:
    return {
        "choices": [
            {"index": 0, "message": {"role": "assistant", **message}, "finish_reason": finish}
        ],
        "usage": {"prompt_tokens": 4, "completion_tokens": 2, "total_tokens": 6},
    }


def _call(identity: str, value: int) -> dict[str, Any]:
    return {
        "id": identity,
        "type": "function",
        "function": {"name": "f", "arguments": json.dumps({"x": value})},
    }


def _chunk(delta: dict[str, Any], finish: str | None = None) -> bytes:
    payload = {"choices": [{"index": 0, "delta": delta, "finish_reason": finish}]}
    return ("data: " + json.dumps(payload, ensure_ascii=False) + "\r\n\r\n").encode()


def _decode(
    adapter: Any, body: dict[str, Any], wire: bytes, *, failure: bool = False
) -> dict[str, Any]:
    decoder = adapter.create_stream_decoder(
        logical_model="logical", request_body=body, metadata={"case": "wire"}
    )
    events = []
    # Fragment both UTF-8 code points and CRLF delimiters, then deliver several events together.
    split = wire.find("é".encode()) + 1 if "é".encode() in wire else 7
    for fragment in (wire[:split], wire[split : split + 3], wire[split + 3 :]):
        events.extend(decoder.feed(fragment))
    error = None
    try:
        events.extend(decoder.finish())
    except ValueError as exc:
        if not failure:
            raise
        error = str(exc)
        events.extend(decoder.build_failure("synthetic stream failure"))
    return {
        "events": [event.decode() for event in events],
        "usage": list(decoder.usage),
        "validated": decoder.validated,
        "error": error,
    }


def capture(case: str) -> Any:  # noqa: PLR0911, PLR0912, PLR0915 -- baseline scenario dispatcher
    adapter = GoogleAiStudioAdapter(profile=_profile())
    body: dict[str, Any] = {"model": "logical", "input": "synthetic"}
    tools_body = {**body, "tools": [TOOL], "parallel_tool_calls": True}
    structured_body = {
        **body,
        "text": {
            "format": {"type": "json_schema", "name": "result", "strict": True, "schema": SCHEMA}
        },
    }
    if case == "rejections":
        bodies = [
            {},
            {"input": ""},
            {"input": 4},
            {**body, "reasoning": {}},
            {**body, "store": True},
            {**body, "stream": "true"},
            {**body, "max_output_tokens": True},
            {**body, "temperature": 3},
            {**body, "metadata": {"bad": 1}},
            {**body, "input": [{"role": "user", "content": []}]},
            {**body, "input": [{"role": "unknown", "content": "synthetic"}]},
            {**body, "tools": [{"type": "custom"}]},
        ]
        results = [asdict(adapter.check_request("responses", value)) for value in bodies]
        results.append(asdict(GoogleAiStudioAdapter().check_request("responses", tools_body)))
        results.append(asdict(adapter.check_request("unknown", body)))
        results.extend(
            asdict(adapter.check_request("embeddings", value))
            for value in (
                {"input": [1]},
                {"input": "x", "encoding_format": "base64"},
                {"input": "x", "dimensions": 0},
            )
        )
        return results
    if case == "requests":
        bodies = [
            {
                **body,
                "instructions": "synthetic system",
                "max_output_tokens": 12,
                "temperature": 0.4,
                "top_p": 0.8,
                "stream": True,
            },
            {**tools_body, "tool_choice": {"type": "function", "name": "f"}},
            structured_body,
            {
                **body,
                "input": [
                    {"role": "user", "content": "ask"},
                    {
                        "type": "function_call",
                        "call_id": "prior",
                        "name": "f",
                        "arguments": '{"x":1}',
                    },
                    {
                        "type": "function_call_output",
                        "call_id": "prior",
                        "output": "synthetic result",
                    },
                ],
                "tools": [TOOL],
            },
        ]
        for value in bodies:
            assert adapter.check_request("responses", value) is None
        return [
            adapter.build_upstream_body(
                "responses", value, deployment="physical", default_output_tokens=32
            )
            for value in bodies
        ]
    if case == "errors":
        return [
            asdict(adapter.translate_error(code, b"synthetic private marker"))
            for code in (400, 401, 403, 404, 429, 500, 503)
        ]
    if case == "embeddings":
        request = {"input": ["one", "two"], "dimensions": 2}
        provider = {
            "data": [{"index": 0, "embedding": [0.5, 1.0]}, {"index": 1, "embedding": [1.5, 2.0]}],
            "usage": {"prompt_tokens": 3},
        }
        return {
            "request": adapter.build_upstream_body(
                "embeddings", request, deployment="physical", default_output_tokens=32
            ),
            "response": asdict(
                adapter.translate_success(
                    "embeddings",
                    provider,
                    logical_model="logical",
                    expected_input_count=2,
                    expected_dimensions=2,
                )
            ),
        }
    if case == "native_ordered":
        adapter = GoogleNativeAdapter(profile=_profile())
        provider = {
            "candidates": [
                {
                    "index": 0,
                    "content": {
                        "role": "model",
                        "parts": [
                            {"text": "before"},
                            {"functionCall": {"id": "native-call", "name": "f", "args": {"x": 1}}},
                            {"text": "after"},
                        ],
                    },
                    "finishReason": "STOP",
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 4,
                "candidatesTokenCount": 2,
                "totalTokenCount": 6,
            },
        }
        result = adapter.translate_success(
            "responses", provider, logical_model="logical", request_body=tools_body
        )
        wire = ("data: " + json.dumps(provider) + "\n\n").encode()
        return {"response": asdict(result), "stream": _decode(adapter, tools_body, wire)}
    if case == "signed_ordered":
        signed = signed_adapter()
        provider = signed_output(
            [
                {"text": "before", "thoughtSignature": "c2ln"},
                {"functionCall": {"id": "call_fixture", "name": "fixture", "args": {}}},
            ]
        )
        return asdict(
            signed.translate_success(
                "responses", provider, logical_model="m", request_body=SIGNED_BODY
            )
        )
    if case == "audio_lifecycle":
        audio = audio_adapter()
        return [
            asdict(
                audio.translate_success(
                    "responses",
                    native([media()] if finish != "SAFETY" else [], finish),
                    logical_model="m",
                    request_body=AUDIO_BODY,
                )
            )
            for finish in ("STOP", "MAX_TOKENS", "SAFETY")
        ]
    if case.startswith("stream_"):
        name = case.removeprefix("stream_")
        delta: dict[str, Any] = {"content": "café"}
        finish = "length" if name == "length" else "stop"
        if name == "parallel":
            body = tools_body
            delta = {"tool_calls": [{"index": i, **_call(f"call-{i}", i)} for i in range(2)]}
            finish = "tool_calls"
        elif name == "structured":
            body, delta = structured_body, {"content": '{"x":1}'}
        elif name == "refusal":
            delta = {"refusal": "synthetic refusal"}
        wire = _chunk(delta)
        if name != "failure":
            wire += _chunk({}, finish)
        if name != "missing_usage":
            wire += b'data: {"choices":[],"usage":{"prompt_tokens":4,"completion_tokens":2}}\n\n'
        if name != "failure":
            wire += b"data: [DONE]\n\n"
        return _decode(adapter, body, wire, failure=name == "failure")
    finish = case if case in {"length", "content_filter"} else "stop"
    message = {"content": "synthetic"}
    if case == "parallel_calls":
        body = tools_body
        message = {"content": None, "tool_calls": [_call("call-1", 1), _call("call-2", 2)]}
        finish = "tool_calls"
    elif case == "structured":
        body, message = structured_body, {"content": '{"x":1}'}
    elif case == "refusal":
        message = {"content": None, "refusal": "synthetic refusal"}
    provider = _chat(message, finish)
    if case == "missing_usage":
        provider.pop("usage")
    return asdict(
        adapter.translate_success(
            "responses",
            provider,
            logical_model="logical",
            request_body=body,
            metadata={"case": "wire"},
        )
    )


def freeze(monkeypatch: pytest.MonkeyPatch) -> None:
    counter = iter(range(1, 1000))
    monkeypatch.setattr(uuid, "uuid4", lambda: uuid.UUID(int=next(counter) << 64))
    monkeypatch.setattr(time, "time", lambda: 1791417600)
    # Fernet IVs only; this is a synthetic test oracle, never runtime configuration.
    monkeypatch.setattr("cryptography.fernet.os.urandom", lambda size: b"\x01" * size)


@pytest.mark.parametrize("case", CASES)
def test_original_google_wire_oracle(case: str, monkeypatch: pytest.MonkeyPatch) -> None:
    freeze(monkeypatch)
    expected = json.loads(ORACLE.read_text())[case]
    actual = json.loads(json.dumps(capture(case)))
    assert actual == expected
