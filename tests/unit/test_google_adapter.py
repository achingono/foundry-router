"""Google AI Studio adapter: strict contracts, translation, and safety regressions."""

from __future__ import annotations

import json

import httpx
import pytest

from foundry_router.api.adapters import get_adapter
from foundry_router.api.adapters.google_ai_studio import (
    GoogleAiStudioAdapter,
    GoogleStreamDecoder,
)
from foundry_router.config import Settings


def _chat_success(text="Hello", finish="stop", prompt=10, completion=5):
    return {
        "id": "chatcmpl-synthetic",
        "object": "chat.completion",
        "created": 1700000000,
        "model": "gemini-2.5-flash",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": finish,
            }
        ],
        "usage": {
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "total_tokens": prompt + completion,
        },
    }


def _chat_chunk(text="", finish=None, usage=None, chunk_id="chatcmpl-s"):
    choice = {"index": 0, "delta": {}, "finish_reason": finish}
    if text:
        choice["delta"] = {"role": "assistant", "content": text}
    payload: dict = {
        "id": chunk_id,
        "object": "chat.completion.chunk",
        "created": 1700000000,
        "model": "gemini-2.5-flash",
        "choices": [choice],
    }
    if usage is not None:
        payload["usage"] = usage
        payload["choices"] = []
    return f"data: {json.dumps(payload)}\n\n".encode()


class TestAdapterValidation:
    def setup_method(self):
        self.adapter: GoogleAiStudioAdapter = get_adapter("google_ai_studio")  # type: ignore[assignment]

    def test_accepts_text_instructions_history(self):
        body = {
            "model": "alias",
            "input": [
                {"role": "system", "content": "sys"},
                {"role": "developer", "content": "dev"},
                {"role": "user", "content": [{"type": "input_text", "text": "hi"}]},
                {"role": "assistant", "content": [{"type": "output_text", "text": "yo"}]},
            ],
            "instructions": "be brief",
            "max_output_tokens": 64,
            "temperature": 0.5,
            "top_p": 0.9,
            "stream": False,
            "store": False,
            "background": False,
            "include": [],
            "metadata": {"trace": "t"},
        }
        assert self.adapter.check_request("responses", body) is None

    @pytest.mark.parametrize(
        "patch",
        [
            {"tools": []},
            {"tool_choice": "auto"},
            {"previous_response_id": "resp_x"},
            {"conversation": {"id": "conv_x"}},
            {"conversation": "conv_x"},
            {"store": True},
            {"background": True},
            {"include": ["extra"]},
            {"text": {"format": {"type": "json"}}},
            {"reasoning": {"effort": "low"}},
            {"stream_options": {"include_usage": True}},
            {"messages": [{"role": "user", "content": "hi"}]},
        ],
    )
    def test_rejects_unsupported_fields(self, patch):
        body = {"model": "alias", "input": "hi"}
        body.update(patch)
        rejection = self.adapter.check_request("responses", body)
        assert rejection is not None
        assert rejection.status_code == 422

    def test_rejects_bad_roles_and_content(self):
        for bad_input in (
            [{"role": "tool", "content": "x"}],
            [{"role": "user", "content": [{"type": "input_image", "text": "x"}]}],
            [{"role": "user"}],
            [{"role": "user", "content": 42}],
            "   ",
            [],
        ):
            rejection = self.adapter.check_request("responses", {"model": "m", "input": bad_input})
            assert rejection is not None

    def test_rejects_bad_scalars(self):
        assert self.adapter.check_request(
            "responses", {"model": "m", "input": "hi", "temperature": 5}
        )
        assert self.adapter.check_request("responses", {"model": "m", "input": "hi", "top_p": 2})
        assert self.adapter.check_request(
            "responses", {"model": "m", "input": "hi", "max_output_tokens": 0}
        )
        assert self.adapter.check_request(
            "responses", {"model": "m", "input": "hi", "stream": "yes"}
        )


class TestUpstreamBuilding:
    def setup_method(self):
        self.adapter: GoogleAiStudioAdapter = get_adapter("google_ai_studio")  # type: ignore[assignment]

    def test_text_input_becomes_user_message_with_limits(self):
        upstream = self.adapter.build_upstream_body(
            "responses",
            {"model": "alias", "input": "hello"},
            deployment="gemini-2.5-flash",
            default_output_tokens=4096,
        )
        assert upstream["model"] == "gemini-2.5-flash"
        assert upstream["messages"] == [{"role": "user", "content": "hello"}]
        assert upstream["max_completion_tokens"] == 4096
        assert "stream_options" not in upstream

    def test_history_instructions_stream_options(self):
        upstream = self.adapter.build_upstream_body(
            "responses",
            {
                "model": "alias",
                "instructions": "sys-inst",
                "input": [
                    {"role": "developer", "content": "dev-inst"},
                    {"role": "user", "content": [{"type": "input_text", "text": "hi"}]},
                ],
                "max_output_tokens": 32,
                "temperature": 0.2,
                "stream": True,
            },
            deployment="gemini-2.5-flash",
            default_output_tokens=4096,
        )
        assert upstream["messages"][0] == {"role": "system", "content": "sys-inst"}
        assert upstream["messages"][1] == {"role": "system", "content": "dev-inst"}
        assert upstream["messages"][2]["content"] == [{"type": "text", "text": "hi"}]
        assert upstream["max_completion_tokens"] == 32
        assert upstream["stream_options"] == {"include_usage": True}

    def test_embeddings_building(self):
        upstream = self.adapter.build_upstream_body(
            "embeddings",
            {"model": "alias", "input": ["a", "b"], "dimensions": 8},
            deployment="gemini-embedding-001",
            default_output_tokens=4096,
        )
        assert upstream == {
            "model": "gemini-embedding-001",
            "input": ["a", "b"],
            "dimensions": 8,
            "encoding_format": "float",
        }


class TestSuccessTranslation:
    def setup_method(self):
        self.adapter: GoogleAiStudioAdapter = get_adapter("google_ai_studio")  # type: ignore[assignment]

    def test_stop_becomes_completed_with_logical_alias(self):
        out = self.adapter.translate_success(
            "responses", _chat_success("Hi", "stop", 12, 3), logical_model="my-alias"
        )
        assert out.body["object"] == "response"
        assert out.body["model"] == "my-alias"
        assert out.body["status"] == "completed"
        assert out.body["output"][0]["content"][0]["text"] == "Hi"
        assert out.body["usage"] == {"input_tokens": 12, "output_tokens": 3, "total_tokens": 15}
        assert (out.input_tokens, out.output_tokens) == (12, 3)

    def test_length_and_content_filter_become_incomplete(self):
        for finish, reason in (
            ("length", "max_output_tokens"),
            ("content_filter", "content_filter"),
        ):
            out = self.adapter.translate_success(
                "responses", _chat_success("partial", finish), logical_model="m"
            )
            assert out.body["status"] == "incomplete"
            assert out.body["incomplete_details"] == {"reason": reason}
            assert out.body["output"][0]["content"][0]["text"] == "partial"

    def test_missing_usage_allowed(self):
        payload = _chat_success()
        del payload["usage"]
        out = self.adapter.translate_success("responses", payload, logical_model="m")
        assert out.body["usage"] is None
        assert (out.input_tokens, out.output_tokens) == (None, None)

    def test_partial_usage_omits_public_usage(self):
        payload = _chat_success()
        payload["usage"] = {"prompt_tokens": 7, "total_tokens": 7}
        out = self.adapter.translate_success("responses", payload, logical_model="m")
        assert out.body["usage"] is None
        assert out.input_tokens == 7
        assert out.output_tokens is None

    @pytest.mark.parametrize(
        "mutate",
        [
            lambda p: p.update({"choices": []}),
            lambda p: p.update({"choices": [{}, {}]}),
            lambda p: p["choices"][0].update({"finish_reason": "tool_calls"}),
            lambda p: p["choices"][0].update({"finish_reason": "mystery"}),
            lambda p: p["choices"][0].update({"message": {"role": "user", "content": "x"}}),
            lambda p: p.update({"usage": {"prompt_tokens": -1, "completion_tokens": 0}}),
            lambda p: p.update({"usage": "nope"}),
            lambda p: p["choices"][0]["message"].update({"tool_calls": [{"id": "1"}]}),
            lambda p: p["choices"][0]["message"].update({"content": 42}),
            lambda p: p["choices"][0]["message"].update({"content": [42]}),
            lambda p: p["choices"][0]["message"].update({"content": [{"type": "input_text"}]}),
        ],
    )
    def test_malformed_envelopes_raise(self, mutate):
        payload = _chat_success()
        mutate(payload)
        with pytest.raises(ValueError):
            self.adapter.translate_success("responses", payload, logical_model="m")

    def test_embeddings_translation(self):
        upstream = {
            "object": "list",
            "data": [
                {"object": "embedding", "index": 0, "embedding": [0.1, 0.2]},
                {"object": "embedding", "index": 1, "embedding": [0.3, 0.4]},
            ],
            "model": "gemini-embedding-001",
            "usage": {"prompt_tokens": 6, "total_tokens": 6},
        }
        out = self.adapter.translate_success(
            "embeddings",
            upstream,
            logical_model="emb-alias",
            expected_input_count=2,
            expected_dimensions=2,
        )
        assert out.body["model"] == "emb-alias"
        assert [d["index"] for d in out.body["data"]] == [0, 1]
        assert out.body["data"][0]["embedding"] == [0.1, 0.2]
        assert (out.input_tokens, out.output_tokens) == (6, 0)

    def test_embeddings_count_mismatch_rejected(self):
        upstream = {
            "object": "list",
            "data": [{"object": "embedding", "index": 0, "embedding": [0.1, 0.2]}],
            "model": "m",
        }
        with pytest.raises(ValueError):
            self.adapter.translate_success(
                "embeddings", upstream, logical_model="m", expected_input_count=2
            )

    def test_embeddings_dimensions_mismatch_rejected(self):
        upstream = {
            "object": "list",
            "data": [
                {"object": "embedding", "index": 0, "embedding": [0.1, 0.2, 0.3]},
                {"object": "embedding", "index": 1, "embedding": [0.4, 0.5, 0.6]},
            ],
            "model": "m",
        }
        with pytest.raises(ValueError):
            self.adapter.translate_success(
                "embeddings",
                upstream,
                logical_model="m",
                expected_input_count=2,
                expected_dimensions=2,
            )

    @pytest.mark.parametrize(
        "mutate",
        [
            lambda p: p["data"][0].update({"index": 1}),
            lambda p: p["data"][0].update({"embedding": [float("inf")]}),
            lambda p: p["data"][1].update({"embedding": [1.0]}),
            lambda p: p.update({"data": []}),
        ],
    )
    def test_embeddings_malformed_raise(self, mutate):
        upstream = {
            "object": "list",
            "data": [
                {"object": "embedding", "index": 0, "embedding": [0.1, 0.2]},
                {"object": "embedding", "index": 1, "embedding": [0.3, 0.4]},
            ],
            "model": "m",
        }
        mutate(upstream)
        with pytest.raises(ValueError):
            self.adapter.translate_success("embeddings", upstream, logical_model="m")

    def test_error_mapping(self):
        assert self.adapter.translate_error(401, None).status_code == 502
        assert self.adapter.translate_error(403, None).status_code == 502
        assert self.adapter.translate_error(429, None).status_code == 429
        assert self.adapter.translate_error(503, None).status_code == 503


class TestStreamDecoder:
    def test_fragmented_multiline_unicode_and_usage(self):
        decoder = GoogleStreamDecoder(logical_model="alias")
        first = _chat_chunk("Hel")
        # Split UTF-8 (é = 2 bytes) across chunks and use CRLF framing.
        snowman = "café 😀".encode()
        second_payload = json.dumps(
            {
                "id": "chatcmpl-s",
                "object": "chat.completion.chunk",
                "created": 1,
                "model": "gemini-2.5-flash",
                "choices": [{"index": 0, "delta": {"content": "lo "}, "finish_reason": None}],
            }
        ).encode()
        events: list[bytes] = []
        events.extend(decoder.feed(first[:5]))
        events.extend(decoder.feed(first[5:]))
        events.extend(decoder.feed(second_payload + b"\r\n\r\n"))
        # Multiline data: two chunks in one event payload.
        events.extend(decoder.feed(snowman[:3]))
        events.extend(decoder.feed(snowman[3:] + b"\n\n"))
        assert decoder.validated
        assert any(b"response.created" in e for e in events)
        assert any(b"response.output_text.delta" in e for e in events)
        # Usage-only final chunk then terminator.
        done_events = decoder.feed(
            _chat_chunk(finish="stop")
            + _chat_chunk(usage={"prompt_tokens": 9, "completion_tokens": 4})
            + b"data: [DONE]\n\n"
        )
        events.extend(done_events)
        assert any(b"response.completed" in e for e in done_events)
        assert decoder.finish() == []
        assert decoder.usage == (9, 4)
        # Duplicate terminator is deterministic without duplicate settlement data.
        assert decoder.feed(b"data: [DONE]\n\n") == []

    def test_keepalive_and_multiple_events_per_chunk(self):
        decoder = GoogleStreamDecoder(logical_model="m")
        events = decoder.feed(
            b": comment\n\n"
            + _chat_chunk("a")
            + _chat_chunk("b", finish="stop")
            + b"data: [DONE]\n\n"
        )
        assert decoder.validated
        assert sum(1 for e in events if b"output_text.delta" in e) == 2
        assert any(b"response.completed" in e for e in events)
        assert decoder.finish() == []

    def test_empty_delta_does_not_validate_and_missing_finish_fails(self):
        decoder = GoogleStreamDecoder(logical_model="m")
        # Role-only delta carries no text or finish: must not commit downstream.
        assert decoder.feed(_chat_chunk()) == []
        assert not decoder.validated
        # Text without any finish reason must never complete successfully.
        decoder.feed(_chat_chunk("hi"))
        with pytest.raises(ValueError):
            decoder.feed(b"data: [DONE]\n\n")

    def test_truncation_and_malformed_never_succeed(self):
        decoder = GoogleStreamDecoder(logical_model="m")
        decoder.feed(_chat_chunk("hi"))
        with pytest.raises(ValueError):
            decoder.finish()
        bad = GoogleStreamDecoder(logical_model="m")
        with pytest.raises(ValueError):
            bad.feed(b"data: {not-json}\n\n")
        with pytest.raises(ValueError):
            bad.feed(_chat_chunk(finish="mystery"))

    def test_bounds(self):
        from foundry_router.api.adapters.google_ai_studio import MAX_GOOGLE_EVENT_BYTES

        decoder = GoogleStreamDecoder(logical_model="m")
        with pytest.raises(ValueError):
            decoder.feed(b"data: " + b"x" * (MAX_GOOGLE_EVENT_BYTES + 1) + b"\n\n")


class TestDecoderFailureEvents:
    def test_failure_preserves_identity_and_sequence(self):
        decoder = GoogleStreamDecoder(logical_model="alias")
        header_events = decoder.feed(_chat_chunk("hi", finish="stop"))
        assert decoder.validated
        last_sequence = max(
            json.loads(e.split(b"data: ", 1)[1])["sequence_number"] for e in header_events
        )
        created = json.loads(header_events[0].split(b"data: ", 1)[1])
        response_id = created["response"]["id"]
        (failed_event,) = decoder.build_failure("Backend stream truncated")
        payload = json.loads(failed_event.split(b"data: ", 1)[1])
        assert payload["type"] == "response.failed"
        assert isinstance(payload["sequence_number"], int)
        assert payload["sequence_number"] > last_sequence
        assert payload["response"]["id"] == response_id
        assert payload["response"]["status"] == "failed"
        assert payload["response"]["error"]["type"] == "upstream_error"

    def test_failure_is_exactly_once(self):
        decoder = GoogleStreamDecoder(logical_model="m")
        decoder.feed(_chat_chunk("hi", finish="stop"))
        assert len(decoder.build_failure("first")) == 1
        assert decoder.build_failure("second") == []
        assert decoder.finish() == []


class TestConfigOperations:
    def test_defaults(self):
        settings = Settings(
            backends_json='{"az": {"endpoint": "https://a.example", "credential": "k", "deployment": "d"}, '
            '"gm": {"provider": "google_ai_studio", "endpoint": "https://g.example", '
            '"credential": "k", "deployment": "gemini-2.5-flash"}}',
            models_json='{"m": {"backends": {"az": 1.0, "gm": 1.0}}}',
            client_api_keys_json='["c"]',
            admin_api_keys_json='["a"]',
            pricing_json="{}",
            backend_cycle_start_day_json="{}",
        )
        assert settings.backends["az"].supported_operations == ["responses", "embeddings"]
        assert settings.backends["gm"].supported_operations == ["responses"]

    @pytest.mark.parametrize(
        "ops",
        [[], ["responses", "responses"], ["chat/completions"], ["responses", "nope"]],
    )
    def test_rejects_bad_operations(self, ops):
        import json as _json

        with pytest.raises(ValueError):
            Settings(
                backends_json=_json.dumps(
                    {
                        "gm": {
                            "provider": "google_ai_studio",
                            "endpoint": "https://g.example",
                            "credential": "k",
                            "deployment": "gemini-2.5-flash",
                            "supported_operations": ops,
                        }
                    }
                ),
                models_json='{"m": {"backends": {"gm": 1.0}}}',
                client_api_keys_json='["c"]',
                admin_api_keys_json='["a"]',
                pricing_json="{}",
                backend_cycle_start_day_json="{}",
            )

    @pytest.mark.parametrize(
        "endpoint",
        [
            "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
            "https://generativelanguage.googleapis.com/v1beta/openai/embeddings",
        ],
    )
    def test_rejects_operation_paths_in_endpoint(self, endpoint):
        import json as _json

        with pytest.raises(ValueError):
            Settings(
                backends_json=_json.dumps(
                    {
                        "gm": {
                            "provider": "google_ai_studio",
                            "endpoint": endpoint,
                            "credential": "k",
                            "deployment": "gemini-2.5-flash",
                        }
                    }
                ),
                models_json='{"m": {"backends": {"gm": 1.0}}}',
                client_api_keys_json='["c"]',
                admin_api_keys_json='["a"]',
                pricing_json="{}",
                backend_cycle_start_day_json="{}",
            )


class TestBackendSecurity:
    async def test_bearer_header_and_query_rejection(self, monkeypatch):
        from foundry_router.backends import AllowedBackendClient

        settings = Settings(
            backends_json='{"gm": {"provider": "google_ai_studio", "endpoint": "https://generativelanguage.googleapis.com", "credential": "AIza-secret", "deployment": "gemini-2.5-flash"}}',
            models_json='{"m": {"backends": {"gm": 1.0}}}',
            client_api_keys_json='["c"]',
            admin_api_keys_json='["a"]',
            pricing_json="{}",
            backend_cycle_start_day_json="{}",
        )
        monkeypatch.setattr("foundry_router.backends.load_settings", lambda: settings)
        client = AllowedBackendClient()
        try:
            headers = client._backend_headers(
                "gm", {"authorization": "Bearer client", "x-goog-api-key": "x"}
            )
            assert headers == {"authorization": "Bearer AIza-secret"}
            url = client._backend_url("gm", "responses")
            assert (
                str(url)
                == "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
            )
            # Double compat suffix must not duplicate.
            settings.backends["gm"].endpoint = httpx.URL(
                "https://generativelanguage.googleapis.com/v1beta/openai"
            )
            client2 = AllowedBackendClient()
            try:
                url2 = client2._backend_url("gm", "responses")
                assert str(url2) == (
                    "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
                )
            finally:
                await client2.aclose()
            import pytest as _pytest

            from foundry_router.backends import SecurityError

            with _pytest.raises(SecurityError):
                await client.get(
                    "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
                    params={"key": "AIza-secret"},
                )
        finally:
            await client.aclose()


class TestCreditEstimates:
    def test_instructions_and_history_in_estimate(self):
        from foundry_router.credit import estimate_request_cost

        pricing = {"m": type("P", (), {"input_per_million": 10.0, "output_per_million": 0.0})()}
        base = estimate_request_cost(
            model="m", operation="responses", body={"input": "hi"}, pricing=pricing
        )
        assert base is not None
        extended = estimate_request_cost(
            model="m",
            operation="responses",
            body={
                "input": [{"role": "user", "content": "hi"}],
                "instructions": "be brief, be correct, be kind",
            },
            pricing=pricing,
        )
        assert extended is not None
        assert extended.input_tokens > base.input_tokens
