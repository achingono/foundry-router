"""Null-tolerant reasoning in translated Chat messages with redacted rejections."""

from __future__ import annotations

import pytest

from foundry_router import forwarding
from foundry_router.api.adapters import get_adapter
from foundry_router.api.adapters.base import TranslatedRejectionError
from foundry_router.api.adapters.compatible_text import (
    CompatibleTextAdapter,
    CompatibleTextStreamDecoder,
    TextRequestContext,
)
from foundry_router.api.adapters.google_ai_studio import GoogleAiStudioAdapter


def chat_envelope(message):
    return {
        "choices": [{"message": message, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 4, "completion_tokens": 2, "total_tokens": 6},
    }


def assistant(content="answer", **extra):
    return {"role": "assistant", "content": content, **extra}


class TestNullReasoningAccepted:
    @pytest.mark.parametrize("reasoning", [None, ""])
    def test_nonstream_null_reasoning_passes_through(self, reasoning):
        adapter = CompatibleTextAdapter()
        upstream = chat_envelope(assistant(reasoning=reasoning))
        translated = adapter.translate_success(
            "responses", upstream, logical_model="logical", request_body={"input": "x"}
        )
        assert translated.input_tokens == 4
        assert translated.body["output"][0]["content"][0]["text"] == "answer"

    def test_stream_null_reasoning_decodes(self):
        decoder = CompatibleTextStreamDecoder(logical_model="logical", context=TextRequestContext())
        chunk = (
            b'data: {"choices":[{"delta":{"role":"assistant","content":"hi",'
            b'"reasoning":null},"finish_reason":"stop"}]}\n\n'
        )
        assert decoder.feed(chunk)

    def test_openrouter_registry_adapter_tolerates_null(self):
        adapter = get_adapter("openrouter")
        assert isinstance(adapter, CompatibleTextAdapter)
        translated = adapter.translate_success(
            "responses",
            chat_envelope(assistant(reasoning=None)),
            logical_model="logical",
            request_body={"input": "x"},
        )
        assert translated.input_tokens == 4


class TestContentBearingRejection:
    def test_nonstream_reasoning_content_rejected(self):
        adapter = CompatibleTextAdapter()
        with pytest.raises(TranslatedRejectionError) as excinfo:
            adapter.translate_success(
                "responses",
                chat_envelope(assistant(reasoning="thinking text")),
                logical_model="logical",
                request_body={"input": "x"},
            )
        assert excinfo.value.fields == ("reasoning",)
        assert "thinking text" not in str(excinfo.value)

    def test_other_unknown_fields_still_rejected(self):
        adapter = CompatibleTextAdapter()
        with pytest.raises(TranslatedRejectionError) as excinfo:
            adapter.translate_success(
                "responses",
                chat_envelope(assistant(custom_field="v")),
                logical_model="logical",
                request_body={"input": "x"},
            )
        assert excinfo.value.fields == ("custom_field",)

    def test_hostile_names_and_values_sanitized(self):
        adapter = CompatibleTextAdapter()
        hostile = "bad\nfield: sk-secret-marker"
        with pytest.raises(TranslatedRejectionError) as excinfo:
            adapter.translate_success(
                "responses",
                chat_envelope(assistant(**{hostile: "sk-secret-marker"})),
                logical_model="logical",
                request_body={"input": "x"},
            )
        assert excinfo.value.fields == ("<unexpected-field>",)
        assert "sk-secret-marker" not in str(excinfo.value)

    def test_stream_reasoning_content_rejected(self):
        decoder = CompatibleTextStreamDecoder(logical_model="logical", context=TextRequestContext())
        chunk = (
            b'data: {"choices":[{"delta":{"content":"hi",'
            b'"reasoning":"thinking"},"finish_reason":"stop"}]}\n\n'
        )
        with pytest.raises(TranslatedRejectionError) as excinfo:
            decoder.feed(chunk)
        assert excinfo.value.fields == ("reasoning",)

    def test_rejection_is_value_error(self):
        assert issubclass(TranslatedRejectionError, ValueError)

    def test_total_entries_bounded(self):
        from foundry_router.api.adapters.openai_compatible import _rejection_fields

        many = {f"field_{index}": None for index in range(20)}
        fields = _rejection_fields(many, frozenset())
        assert len(fields) <= 8
        assert fields[-1] == "<unexpected-field>"

    def test_exception_immutable(self):
        import dataclasses

        exc = TranslatedRejectionError("unsupported", fields=("reasoning",))
        with pytest.raises(dataclasses.FrozenInstanceError):
            exc.fields = ()
        with pytest.raises(dataclasses.FrozenInstanceError):
            exc.message = "other"


class TestGoogleUnchanged:
    def test_google_adapter_stays_strict_on_null_reasoning(self):
        adapter = GoogleAiStudioAdapter()
        with pytest.raises(ValueError):
            adapter.translate_success(
                "responses",
                chat_envelope(assistant(reasoning=None)),
                logical_model="logical",
                request_body={"input": "x"},
            )


class TestRejectionLogging:
    def test_fields_logged_without_values(self, monkeypatch):
        calls = []

        class StubLogger:
            def debug(self, *args, **kwargs):
                calls.append((args, kwargs))

        monkeypatch.setattr(forwarding, "_logger", StubLogger())
        forwarding._log_translated_rejection(
            TranslatedRejectionError("unsupported", fields=("reasoning",)),
            operation="responses",
            backend_id="backend_a",
        )
        assert len(calls) == 1
        _, kwargs = calls[0]
        assert kwargs["fields"] == ["reasoning"]
        assert kwargs["operation"] == "responses"
        assert kwargs["backend"] == "backend_a"

    def test_no_fields_no_log(self, monkeypatch):
        calls = []

        class StubLogger:
            def debug(self, *args, **kwargs):
                calls.append((args, kwargs))

        monkeypatch.setattr(forwarding, "_logger", StubLogger())
        forwarding._log_translated_rejection(ValueError("plain"), operation="responses")
        assert calls == []

    def test_logger_never_raises_on_hostile_exception(self, monkeypatch):
        calls = []

        class StubLogger:
            def debug(self, *args, **kwargs):
                calls.append((args, kwargs))

        monkeypatch.setattr(forwarding, "_logger", StubLogger())

        class HostileError(Exception):
            @property
            def fields(self):
                raise RuntimeError("boom")

        forwarding._log_translated_rejection(HostileError(), operation="responses")
        assert calls == []
