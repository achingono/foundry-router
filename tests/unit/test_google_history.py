"""Signed history projection preserves native Part identity and shallow carrier semantics."""

import pytest

from foundry_router.api.adapters.google_schema import load_bounded_json
from foundry_router.api.google_history import carrier_tokens, project_history, project_item
from foundry_router.api.google_state import ProviderStateError, canonical_wire_bytes

STATE = {"version": 1, "token": "fixture.token"}
CALL = {
    "type": "function_call",
    "id": "fc_fixture",
    "call_id": "call_fixture",
    "name": "fixture",
    "arguments": '{"foundry_provider_state":"inert"}',
    "status": "completed",
    "foundry_provider_state": STATE,
}
MESSAGE = {
    "type": "message",
    "id": "msg_fixture",
    "role": "assistant",
    "status": "completed",
    "content": [{"type": "output_text", "text": "fixture", "annotations": []}],
    "foundry_provider_state": STATE,
}


def test_projection_exact_arguments_defaults_order_and_owned_snapshot():
    user = {"role": "user", "content": "fixture"}
    body = {"input": [user, CALL, MESSAGE]}
    items, digests = project_history(body)
    assert items[0] == {**user, "type": "message", "status": "completed"}
    assert items[1]["arguments"] == CALL["arguments"]
    assert "foundry_provider_state" not in items[1]
    assert len(digests) == 3
    body["input"][2]["content"][0]["text"] = "changed"
    assert items[2]["content"][0]["text"] == "fixture"
    MESSAGE["content"][0]["text"] = "fixture"


@pytest.mark.parametrize("depth", [30, 31, 32, 33])
def test_projection_empty_depth_preserves_original_scanner_acceptance(depth):
    content = []
    for _ in range(depth - 1):
        content = [content]
    item = {"role": "user", "content": content}
    projected = {**item, "type": "message", "status": "completed"}
    if depth <= 31:
        expected = load_bounded_json(canonical_wire_bytes(projected).decode(), max_bytes=2097152)
        assert project_item(item) == expected
    else:
        with pytest.raises(ValueError):
            project_item(item)
        with pytest.raises(ValueError):
            load_bounded_json(canonical_wire_bytes(projected).decode(), max_bytes=2097152)


def test_projection_tuple_mapping_and_subclass_children_are_owned():
    class PlainDict(dict):
        pass

    child = PlainDict(values=([1],))
    snapshot = project_item({"role": "user", "content": [child]})
    child["values"][0].append(2)
    assert snapshot["content"] == [{"values": [[1]]}]


def test_projection_duplicate_emitting_subclass_still_rejects():
    class DuplicateDict(dict):
        def items(self):
            return [("x", 1), ("x", 2)]

    with pytest.raises(ValueError):
        project_item({"role": "user", "content": [DuplicateDict(x=1)]})


@pytest.mark.parametrize(
    "item",
    [
        None,
        {"type": "unknown"},
        {"role": "unknown", "content": "fixture"},
        {"role": "user", "content": "fixture", "foundry_provider_state": STATE},
        {"role": "user", "content": "fixture", "status": None},
        {"role": "user", "content": "fixture", "id": None},
        {**CALL, "status": "incomplete"},
        {**CALL, "id": ""},
        {key: value for key, value in CALL.items() if key != "call_id"},
        {**CALL, "arguments": {}},
        {**MESSAGE, "content": "fixture"},
        {**MESSAGE, "content": [{"type": "output_text", "text": "fixture", "annotations": [1]}]},
        {**MESSAGE, "content": [{"type": "output_text", "text": "", "annotations": []}]},
        {key: value for key, value in MESSAGE.items() if key != "id"},
        {"type": "function_call_output", "call_id": "fixture", "output": 1},
    ],
)
def test_unsupported_projection_shapes_reject(item):
    with pytest.raises(ProviderStateError):
        project_item(item)


def test_plain_url_result_stays_inert_and_reserved_nested_content_is_preserved():
    result = {
        "type": "function_call_output",
        "call_id": "fixture",
        "output": "https://fixture.invalid/foundry_provider_state",
    }
    assert project_item(result)["output"] == result["output"]
    item = {
        "role": "user",
        "content": [
            {"type": "input_text", "text": "fixture", "nested": {"foundry_provider_state": "inert"}}
        ],
    }
    assert project_item(item)["content"] == item["content"]


def test_carrier_occurrences_count_before_deduplication():
    body = {
        "foundry_provider_state": {"version": 1},
        "input": [{"role": "user", "content": "fixture"}, CALL, MESSAGE],
    }
    assert carrier_tokens(body) == ("fixture.token", "fixture.token")
    body["input"] = [{**CALL, "foundry_provider_state": {"version": 1, "token": "x" * 131072}}] * 5
    with pytest.raises(ProviderStateError):
        carrier_tokens(body)


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"input": "fixture"},
        {"foundry_provider_state": {"version": True}, "input": [CALL]},
        {"foundry_provider_state": {"version": 1}, "input": [None]},
        {
            "foundry_provider_state": {"version": 1},
            "input": [
                {key: value for key, value in CALL.items() if key != "foundry_provider_state"}
            ],
        },
        {
            "foundry_provider_state": {"version": 1},
            "input": [{"role": "user", "content": "fixture", "foundry_provider_state": STATE}],
        },
        {
            "foundry_provider_state": {"version": 1},
            "input": [{**CALL, "foundry_provider_state": {"version": 1, "token": "é"}}],
        },
    ],
)
def test_missing_stripped_or_malformed_carriers_reject(body):
    with pytest.raises(ProviderStateError):
        carrier_tokens(body)


def test_unique_turn_and_history_caps():
    body = {
        "foundry_provider_state": {"version": 1},
        "input": [
            {**CALL, "foundry_provider_state": {"version": 1, "token": f"fixture.{i}"}}
            for i in range(17)
        ],
    }
    with pytest.raises(ProviderStateError):
        carrier_tokens(body)
    for history in ([], "fixture", [CALL] * 257):
        with pytest.raises(ProviderStateError):
            project_history({"input": history})


@pytest.mark.parametrize("field", ["id", "call_id", "name", "arguments"])
def test_surrogate_call_values_fail_safely(field):
    with pytest.raises(ProviderStateError):
        project_item({**CALL, field: "\ud800"})


def test_context_defaults_and_generation_settings():
    from foundry_router.api.google_history import project_context
    from foundry_router.config.google_features import GoogleFeatureProfile

    profile = GoogleFeatureProfile()
    assert project_context({"model": "fixture", "input": []}, profile) == project_context(
        {"model": "fixture", "input": [], "instructions": "", "text": {"format": {"type": "text"}}},
        profile,
    )
    for changes in ({"instructions": None}, {"temperature": 0.5}, {"metadata": {"x": "a" * 128}}):
        with pytest.raises(ProviderStateError):
            project_context({"model": "fixture", "input": [], **changes}, profile)
