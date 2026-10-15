"""Anthropic text contract, usage integrity and configuration boundaries."""

import pytest

from foundry_router.api.adapters.opencode_anthropic import OpenCodeAnthropicAdapter, anthropic_usage
from foundry_router.config import BackendConfig

ADAPTER = OpenCodeAnthropicAdapter()
CONFIG = {
    "provider": "opencode_anthropic",
    "endpoint": "https://zen.example.test/inference/v1",
    "credential": "synthetic-key",
    "deployment": "arbitrary-model",
}


def message():
    return {
        "id": "m",
        "type": "message",
        "role": "assistant",
        "model": "physical",
        "content": [{"type": "text", "text": "answer"}],
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {
            "input_tokens": 10,
            "output_tokens": 5,
            "cache_creation_input_tokens": 3,
            "cache_read_input_tokens": 2,
        },
    }


def test_native_request_and_defaults():
    body = {
        "model": "logical",
        "input": [{"role": "developer", "content": "rules"}, {"role": "user", "content": "hi"}],
        "instructions": "system",
        "store": False,
        "stream": False,
        "metadata": {"tag": "local"},
    }
    out = ADAPTER.build_upstream_body(
        "responses", body, deployment="physical", default_output_tokens=128
    )
    assert out == {
        "model": "physical",
        "system": [{"type": "text", "text": "system"}, {"type": "text", "text": "rules"}],
        "messages": [{"role": "user", "content": [{"type": "text", "text": "hi"}]}],
        "max_tokens": 128,
    }


@pytest.mark.parametrize(
    "extra",
    [
        {"stream": True},
        {"thinking": {}},
        {"tools": []},
        {"cache_control": {}},
        {"max_tokens": 128},
        {"temperature": 2},
        {"temperature": 0.5, "top_p": 0.7},
        {"previous_response_id": "m"},
    ],
)
def test_reject_before_assembly(extra):
    body = {"model": "m", "input": "hello", **extra}
    assert ADAPTER.check_request("responses", body) is not None
    with pytest.raises(ValueError):
        ADAPTER.build_upstream_body(
            "responses", body, deployment="physical", default_output_tokens=128
        )


def test_reject_system_only_and_stream_decoder():
    assert (
        ADAPTER.check_request("responses", {"input": [{"role": "system", "content": "x"}]})
        is not None
    )
    assert ADAPTER.check_request("embeddings", {"input": "x"}) is not None
    with pytest.raises(ValueError, match="streaming"):
        ADAPTER.create_stream_decoder(logical_model="m")


@pytest.mark.parametrize("extra", [{"temperature": 0.5}, {"top_p": 0.5}])
def test_one_sampling_parameter(extra):
    out = ADAPTER.build_upstream_body(
        "responses", {"input": "x", **extra}, deployment="m", default_output_tokens=128
    )
    assert all(out[k] == v for k, v in extra.items())


def test_cache_usage_and_nonstream_conversion():
    out = ADAPTER.translate_success(
        "responses", message(), logical_model="logical", metadata={"tag": "local"}
    )
    assert out.body["usage"] == {"input_tokens": 15, "output_tokens": 5, "total_tokens": 20}
    assert out.body["metadata"] == {"tag": "local"}
    assert out.body["model"] == "logical"
    assert ADAPTER.extract_usage("responses", message()) == (15, 5)


@pytest.mark.parametrize(
    "reason,status",
    [("stop_sequence", "completed"), ("max_tokens", "incomplete"), ("refusal", "incomplete")],
)
def test_terminal_reason_mapping(reason, status):
    raw = message()
    raw["stop_reason"] = reason
    out = ADAPTER.translate_success("responses", raw, logical_model="m")
    assert out.body["status"] == status
    if reason == "refusal":
        assert "answer" not in str(out.body)


@pytest.mark.parametrize(
    "mutate", ["unknown", "bad_role", "bad_block", "empty", "reason", "oversize"]
)
def test_invalid_output_preserves_known_cache_usage(mutate):
    raw = message()
    if mutate == "unknown":
        raw["unknown"] = "secret"
    if mutate == "bad_role":
        raw["role"] = "user"
    if mutate == "bad_block":
        raw["content"] = [{"type": "thinking", "thinking": "private"}]
    if mutate == "empty":
        raw["content"] = []
    if mutate == "reason":
        raw["stop_reason"] = "tool_use"
    if mutate == "oversize":
        raw["content"] = [{"type": "text", "text": "x" * (4 * 1024 * 1024 + 1)}]
    assert anthropic_usage(raw) == (15, 5)
    with pytest.raises(ValueError):
        ADAPTER.translate_success("responses", raw, logical_model="m")


@pytest.mark.parametrize("value", [True, -1, 1.5, "3", None, 1000000001])
def test_invalid_usage_is_not_a_zero_cost(value):
    raw = message()
    raw["usage"]["cache_creation_input_tokens"] = value
    assert anthropic_usage(raw) == (None, None)
    with pytest.raises(ValueError):
        ADAPTER.translate_success("responses", raw, logical_model="m")


@pytest.mark.parametrize(
    "delta",
    [
        {"credit_metered": False},
        {"api_surface": "native"},
        {"google_features": {"features": ["json_object"]}},
        {"deployment": "a/b"},
        {"deployment": "a?x"},
        {"deployment": "a" * 513},
        {"endpoint": "https://zen.example.test/inference/v1/messages"},
        {"endpoint": "https://zen.example.test/a/../v1"},
        {"supported_operations": ["embeddings"]},
    ],
)
def test_config_confinement(delta):
    with pytest.raises(ValueError):
        BackendConfig.model_validate({**CONFIG, **delta})


def test_config_defaults():
    assert BackendConfig.model_validate(CONFIG).supported_operations == ["responses"]


def test_explicit_nulls_use_native_defaults():
    out = ADAPTER.build_upstream_body(
        "responses",
        {"input": "x", "max_output_tokens": None, "temperature": None, "top_p": None},
        deployment="m",
        default_output_tokens=128,
    )
    assert out["max_tokens"] == 128 and "temperature" not in out and "top_p" not in out
    out = ADAPTER.build_upstream_body(
        "responses",
        {"input": "x", "temperature": None, "top_p": 0.5},
        deployment="m",
        default_output_tokens=128,
    )
    assert out["top_p"] == 0.5 and "temperature" not in out


@pytest.mark.parametrize("citations", [None, []])
def test_absent_optional_metadata_is_dropped(citations):
    raw = message()
    raw.update(container=None, diagnostics=None, stop_details=None)
    raw["content"][0]["citations"] = citations
    out = ADAPTER.translate_success("responses", raw, logical_model="logical")
    assert out.body["usage"]["input_tokens"] == 15
    assert not {"container", "diagnostics", "stop_details", "citations"} & set(out.body)


@pytest.mark.parametrize("field", ["container", "diagnostics", "stop_details"])
@pytest.mark.parametrize("value", [False, {}, [], "private-state"])
def test_nonnull_optional_state_still_rejects(field, value):
    raw = message()
    raw[field] = value
    assert anthropic_usage(raw) == (15, 5)
    with pytest.raises(ValueError):
        ADAPTER.translate_success("responses", raw, logical_model="logical")


@pytest.mark.parametrize("value", [False, {}, (), "state", [{"type": "citation"}]])
def test_nonempty_or_wrong_type_citations_rejected(value):
    raw = message()
    raw["content"][0]["citations"] = value
    with pytest.raises(ValueError):
        ADAPTER.translate_success("responses", raw, logical_model="logical")
