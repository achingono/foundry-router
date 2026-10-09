"""Unit tests for the OpenCode Zen Responses adapter."""

from __future__ import annotations

import pytest

from foundry_router.api.adapters.zen import ZenAdapter


@pytest.fixture
def adapter() -> ZenAdapter:
    return ZenAdapter()


def _body(**overrides) -> dict:
    body: dict = {"model": "gpt-5.4", "input": "hello"}
    body.update(overrides)
    return body


class TestZenValidation:
    def test_minimal_string_input_accepted(self, adapter: ZenAdapter) -> None:
        assert adapter.check_request("responses", _body()) is None

    def test_full_stateless_text_accepted(self, adapter: ZenAdapter) -> None:
        body = _body(
            input=[{"role": "system", "content": "be brief"}, {"role": "user", "content": [{"type": "input_text", "text": "hi"}]}],
            instructions="follow policy",
            metadata={"trace": "abc"},
            max_output_tokens=64,
            temperature=0.5,
            top_p=0.9,
            stream=False,
            store=False,
            background=False,
        )
        assert adapter.check_request("responses", body) is None

    def test_non_responses_operation_rejected(self, adapter: ZenAdapter) -> None:
        rejection = adapter.check_request("embeddings", _body())
        assert rejection is not None
        assert rejection.code == "unsupported_operation"

    @pytest.mark.parametrize(
        "field",
        [
            "tools",
            "tool_choice",
            "text",
            "reasoning",
            "previous_response_id",
            "conversation",
            "include",
            "stream_options",
            "messages",
            "max_tokens",
            "max_completion_tokens",
            "contents",
            "generationConfig",
        ],
    )
    def test_foreign_fields_rejected_alone_and_with_valid_input(
        self, adapter: ZenAdapter, field: str
    ) -> None:
        assert adapter.check_request("responses", {field: "x"}) is not None
        rejection = adapter.check_request("responses", _body(**{field: "x"}))
        assert rejection is not None
        assert rejection.status_code == 422

    @pytest.mark.parametrize("flag", ["store", "background"])
    def test_true_state_flags_rejected(self, adapter: ZenAdapter, flag: str) -> None:
        assert adapter.check_request("responses", _body(**{flag: True})) is not None
        assert adapter.check_request("responses", _body(**{flag: False})) is None

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"max_output_tokens": 0},
            {"max_output_tokens": 200000},
            {"max_output_tokens": True},
            {"temperature": 3},
            {"temperature": float("nan")},
            {"top_p": -0.1},
            {"top_p": "high"},
            {"stream": "yes"},
            {"instructions": 42},
            {"metadata": "trace"},
            {"metadata": {f"k{i}": "v" for i in range(17)}},
            {"input": ""},
            {"input": "   "},
            {"input": []},
            {"input": [{"role": "user", "content": ""}]},
            {
                "input": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_image", "image_url": "https://x/y.png"}
                        ],
                    }
                ]
            },
        ],
    )
    def test_invalid_values_rejected(self, adapter: ZenAdapter, kwargs: dict) -> None:
        assert adapter.check_request("responses", _body(**kwargs)) is not None

    def test_history_item_bound(self, adapter: ZenAdapter) -> None:
        body = _body(
            input=[{"role": "user", "content": "x"} for _ in range(129)],
        )
        assert adapter.check_request("responses", body) is not None

    def test_text_part_bound(self, adapter: ZenAdapter) -> None:
        body = _body(
            input=[
                {
                    "role": "user",
                    "content": [{"type": "text", "text": "x"} for _ in range(129)],
                }
            ],
        )
        assert adapter.check_request("responses", body) is not None

    def test_aggregate_byte_bound(self, adapter: ZenAdapter) -> None:
        body = _body(input="x" * (256 * 1024 + 1))
        assert adapter.check_request("responses", body) is not None


class TestZenTranslation:
    def test_build_upstream_body_substitutes_model_only(self, adapter: ZenAdapter) -> None:
        body = _body(input="hello", temperature=0.5)
        upstream = adapter.build_upstream_body(
            "responses", body, deployment="gpt-5.4", default_output_tokens=1024
        )
        assert upstream == {"model": "gpt-5.4", "input": "hello", "temperature": 0.5}
        assert "max_completion_tokens" not in upstream
        assert "stream_options" not in upstream

    def test_build_upstream_body_rejects_other_operations(
        self, adapter: ZenAdapter
    ) -> None:
        with pytest.raises(ValueError, match="only the Responses operation"):
            adapter.build_upstream_body(
                "embeddings", _body(), deployment="gpt-5.4", default_output_tokens=8
            )

    def test_translate_success_is_identity_with_usage(self, adapter: ZenAdapter) -> None:
        upstream = {
            "id": "resp_1",
            "model": "gpt-5.4",
            "output": [],
            "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
        }
        translated = adapter.translate_success("responses", upstream, logical_model="gpt-5.4")
        assert translated.body == upstream
        assert (translated.input_tokens, translated.output_tokens) == (10, 5)

    def test_translate_success_tolerates_missing_usage(self, adapter: ZenAdapter) -> None:
        translated = adapter.translate_success(
            "responses", {"id": "resp_1"}, logical_model="gpt-5.4"
        )
        assert (translated.input_tokens, translated.output_tokens) == (None, None)

    def test_translate_success_rejects_non_object(self, adapter: ZenAdapter) -> None:
        with pytest.raises(ValueError):
            adapter.translate_success("responses", [1], logical_model="gpt-5.4")

    @pytest.mark.parametrize(
        "status,code",
        [(429, "rate_limit_exceeded"), (500, "upstream_error"), (400, "upstream_error")],
    )
    def test_translate_error_mapping(
        self, adapter: ZenAdapter, status: int, code: str
    ) -> None:
        assert adapter.translate_error(status, None).code == code

    def test_stream_decoder_raises(self, adapter: ZenAdapter) -> None:
        with pytest.raises(NotImplementedError):
            adapter.create_stream_decoder(logical_model="gpt-5.4")
