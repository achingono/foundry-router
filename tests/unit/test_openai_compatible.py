"""Generic translation reuse, fail-closed hooks, import boundary and compatibility."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from foundry_router.api import adapters
from foundry_router.api.adapters import google_ai_studio, openai_compatible
from foundry_router.api.adapters.google_tools import request_context
from foundry_router.config.google_features import GoogleFeatureProfile
from tests.typing.openai_compatible_context import (
    TextAdapter,
    TextContext,
    accepts_common_context,
)


@pytest.mark.parametrize(
    "hook", ["request_context", "permits", "build_messages", "translate_calls"]
)
def test_base_hooks_fail_closed(hook):
    adapter = openai_compatible.OpenAICompatibleAdapter[TextContext]()
    args = ({},) if hook == "request_context" else ({}, TextContext())
    kwargs = {"completed": True, "refusal": False} if hook == "translate_calls" else {}
    with pytest.raises(NotImplementedError):
        getattr(adapter, hook)(*args, **kwargs)


def test_base_decoder_hook_and_context_are_required():
    with pytest.raises(TypeError):
        openai_compatible.OpenAICompatibleStreamDecoder(logical_model="logical")
    decoder = openai_compatible.OpenAICompatibleStreamDecoder(
        logical_model="logical", context=TextContext()
    )
    with pytest.raises(NotImplementedError):
        decoder._translate_calls([], completed=True, refusal=False)


def test_text_subclass_round_trip_and_capability_gate():
    adapter = TextAdapter()
    body = {"input": "synthetic", "stream": True, "max_output_tokens": 8}
    assert adapter.check_request("responses", body) is None
    upstream = adapter.build_upstream_body(
        "responses", body, deployment="configured", default_output_tokens=16
    )
    assert upstream == {
        "model": "configured",
        "messages": [{"role": "user", "content": "synthetic"}],
        "max_completion_tokens": 8,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    provider = {
        "choices": [
            {"message": {"role": "assistant", "content": "answer"}, "finish_reason": "stop"}
        ],
        "usage": {"prompt_tokens": 3, "completion_tokens": 2},
    }
    translated = adapter.translate_success(
        "responses", provider, logical_model="logical", request_body=body
    )
    assert translated.body["output"][0]["content"][0]["text"] == "answer"
    assert (translated.input_tokens, translated.output_tokens) == (3, 2)
    decoder = adapter.create_stream_decoder(logical_model="logical", request_body=body)
    wire = b'data: {"choices":[{"delta":{"content":"answer"},"finish_reason":"stop"}]}\n\ndata: {"choices":[],"usage":{"prompt_tokens":3,"completion_tokens":2}}\n\ndata: [DONE]\n\n'
    events = decoder.feed(wire) + decoder.finish()
    terminal = json.loads(events[-1].decode().split("data: ")[1])
    assert terminal["type"] == "response.completed"
    assert terminal["response"]["usage"]["total_tokens"] == 5
    assert terminal["response"]["output"][0]["content"][0]["text"] == "answer"
    assert decoder.validated and decoder.usage == (3, 2)
    assert adapter.check_request("responses", {**body, "tools": []}) is not None
    with pytest.raises(ValueError, match="Synthetic request features are disabled"):
        adapter.build_upstream_body(
            "responses", {**body, "tools": []}, deployment="configured", default_output_tokens=16
        )


def test_provider_label_in_rejection_and_stream_errors():
    adapter = TextAdapter()
    assert (
        adapter.check_request("responses", {"input": "x", "reasoning": {}}).message
        == "Unsupported field 'reasoning' for Synthetic backends"
    )
    assert (
        adapter.check_request("responses", {"input": "x", "store": True}).message
        == "Stored responses are not supported for Synthetic backends"
    )
    assert (
        adapter.check_request("responses", {"input": [{"role": "user", "content": "x"}]}).message
        == "Invalid or unsupported Synthetic tools, schema, media or history"
    )
    with pytest.raises(ValueError, match="Synthetic success body must be a JSON object"):
        adapter.translate_success("responses", [], logical_model="logical")
    decoder = adapter.create_stream_decoder(logical_model="logical")
    with pytest.raises(ValueError, match="Malformed Synthetic stream event"):
        decoder.feed(b"data: invalid\n\n")
    with pytest.raises(ValueError, match="Unsupported Synthetic finish reason"):
        adapter.translate_success(
            "responses",
            {"choices": [{"message": {"content": "x"}, "finish_reason": "unknown"}]},
            logical_model="logical",
        )
    decoder = adapter.create_stream_decoder(logical_model="logical")
    with pytest.raises(ValueError, match="Unsupported Synthetic finish reason"):
        decoder.feed(b'data: {"choices":[{"delta":{},"finish_reason":"unknown"}]}\n\n')


def test_generic_import_boundary_and_google_compatibility_exports():
    module = ast.parse(Path(openai_compatible.__file__).read_text())
    allowed_annotation = "foundry_router.api.google_pdf"
    imports = [
        node
        for node in ast.walk(module)
        if isinstance(node, ast.ImportFrom) and node.module and "google" in node.module
    ]
    assert [node.module for node in imports] == [allowed_annotation]
    guard = next(node for node in module.body if isinstance(node, ast.If))
    assert isinstance(guard.test, ast.Name) and guard.test.id == "TYPE_CHECKING"
    assert imports[0] in guard.body
    assert [name.name for name in imports[0].names] == ["PreparedGoogleMedia"]
    assert not any(
        isinstance(node, ast.Import) and any("google" in alias.name for alias in node.names)
        for node in ast.walk(module)
    )
    assert adapters.OpenAICompatibleAdapter is openai_compatible.OpenAICompatibleAdapter
    assert adapters.OpenAICompatibleStreamDecoder is openai_compatible.OpenAICompatibleStreamDecoder
    assert adapters.GoogleAiStudioAdapter is google_ai_studio.GoogleAiStudioAdapter
    assert adapters.GoogleStreamDecoder is google_ai_studio.GoogleStreamDecoder
    for suffix in ("EVENT_BYTES", "ASSEMBLED_TEXT_BYTES", "SSE_BUFFER_BYTES"):
        assert getattr(google_ai_studio, "MAX_GOOGLE_" + suffix) == getattr(
            openai_compatible, "MAX_OPENAI_" + suffix
        )
    accepts_common_context(request_context({}, GoogleFeatureProfile()))


def test_google_optional_context_and_dynamic_decoder_state():
    decoder = google_ai_studio.GoogleStreamDecoder(logical_model="logical")
    decoder.prefetch_finished = True
    assert decoder.prefetch_finished
    assert callable(decoder._context.validate_arguments)
