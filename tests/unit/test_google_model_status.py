"""Documented response metadata is bounded, validated and never forwarded."""

import json

import pytest

from foundry_router.api.adapters.google_native import GoogleNativeAdapter
from foundry_router.config.google_features import GoogleFeatureProfile


def adapter():
    return GoogleNativeAdapter(
        profile=GoogleFeatureProfile(native_thinking_level="low", thought_token_pricing=True)
    )


def response(status):
    return {
        "modelStatus": status,
        "candidates": [
            {
                "content": {
                    "role": "model",
                    "parts": [{"text": "synthetic answer", "thoughtSignature": "opaque"}],
                },
                "finishReason": "STOP",
            }
        ],
        "usageMetadata": {"promptTokenCount": 7, "candidatesTokenCount": 1, "totalTokenCount": 8},
    }


def stream(body):
    return f"data: {json.dumps(body)}\n\n".encode()


@pytest.mark.parametrize(
    "status",
    [
        {},
        {"modelStage": "PREVIEW"},
        {
            "modelStage": "STABLE",
            "message": "private provider metadata",
            "retirementTime": "2027-01-01T00:00:00Z",
        },
    ],
)
def test_metadata_dropped_in_nonstream_and_stream(status):
    raw = response(status)
    a = adapter()
    result = a.translate_success("responses", raw, logical_model="logical")
    assert result.body["usage"]["input_tokens"] == 7
    assert "modelStatus" not in json.dumps(result.body)
    assert "private provider metadata" not in json.dumps(result.body)
    decoder = a.create_stream_decoder(logical_model="logical")
    events = decoder.feed(stream(raw)) + decoder.finish()
    wire = b"".join(events)
    assert b"response.completed" in wire
    assert b"modelStatus" not in wire and b"private provider metadata" not in wire
    assert decoder.usage == (7, 1)


@pytest.mark.parametrize(
    "status",
    [
        None,
        [],
        "x",
        {"modelStage": "UNKNOWN"},
        {"modelStage": []},
        {"message": True},
        {"retirementTime": {}},
        {"extra": "x"},
        {"message": "x" * 4097},
        {"retirementTime": "x" * 129},
    ],
)
def test_invalid_metadata_rejected_in_all_envelopes(status):
    raw = response(status)
    a = adapter()
    with pytest.raises(ValueError):
        a.translate_success("responses", raw, logical_model="logical")
    for payload in (raw, {"modelStatus": status, "usageMetadata": raw["usageMetadata"]}):
        decoder = a.create_stream_decoder(logical_model="logical")
        with pytest.raises(ValueError):
            decoder.feed(stream(payload))
        assert decoder.usage == (7, 1)


def test_usage_only_metadata_validated_before_return():
    decoder = adapter().create_stream_decoder(logical_model="logical")
    assert (
        decoder.feed(
            stream(
                {
                    "modelStatus": {"modelStage": "STABLE"},
                    "usageMetadata": {
                        "promptTokenCount": 7,
                        "candidatesTokenCount": 1,
                        "totalTokenCount": 8,
                    },
                }
            )
        )
        == []
    )
    assert decoder.usage == (7, 1)


def test_unknown_envelope_still_rejected():
    raw = response({"modelStage": "STABLE"})
    raw["unknown"] = "x"
    with pytest.raises(ValueError):
        adapter().translate_success("responses", raw, logical_model="logical")


@pytest.mark.parametrize(
    "timestamp",
    ["2026-10-14T01:10:00Z", "2026-10-14T01:10:00.123456789Z", "2026-10-13T21:10:00-04:00"],
)
def test_vertex_creation_time_validated_and_dropped(timestamp):
    raw = response({"modelStage": "PREVIEW"})
    raw["createTime"] = timestamp
    a = adapter()
    assert "createTime" not in json.dumps(
        a.translate_success("responses", raw, logical_model="logical").body
    )
    decoder = a.create_stream_decoder(logical_model="logical")
    wire = b"".join(decoder.feed(stream(raw)) + decoder.finish())
    assert b"createTime" not in wire and timestamp.encode() not in wire
    decoder = a.create_stream_decoder(logical_model="logical")
    assert (
        decoder.feed(stream({"createTime": timestamp, "usageMetadata": raw["usageMetadata"]})) == []
    )


@pytest.mark.parametrize(
    "timestamp",
    [
        None,
        {},
        123,
        "",
        "2026-10-14T01:10:00",
        "2026-99-14T01:10:00Z",
        "2026-10-14T25:10:00Z",
        "2026-10-14T01:10:00Z\n",
        "2026-10-14T01:10:00+99:00",
        "x" * 129,
    ],
)
def test_vertex_invalid_time_rejected_in_every_envelope(timestamp):
    raw = response({})
    raw["createTime"] = timestamp
    a = adapter()
    with pytest.raises(ValueError):
        a.translate_success("responses", raw, logical_model="logical")
    for payload in (raw, {"createTime": timestamp, "usageMetadata": raw["usageMetadata"]}):
        with pytest.raises(ValueError):
            a.create_stream_decoder(logical_model="logical").feed(stream(payload))


@pytest.mark.parametrize("timestamp", ["2026-10-14T01:10:00+00:60", "2026-10-14T01:10:00-04:99"])
def test_offset_minutes_rejected_in_all_paths(timestamp):
    raw = response({})
    raw["createTime"] = timestamp
    with pytest.raises(ValueError):
        adapter().translate_success("responses", raw, logical_model="logical")
    for data in (raw, {"createTime": timestamp, "usageMetadata": raw["usageMetadata"]}):
        with pytest.raises(ValueError):
            adapter().create_stream_decoder(logical_model="logical").feed(stream(data))


def chunk(text, usage, finish=None):
    candidate = {"content": {"role": "model", "parts": [{"text": text}]}}
    if finish is not None:
        candidate["finishReason"] = finish
    return {"candidates": [candidate], "usageMetadata": usage}


def valid_usage():
    return {"promptTokenCount": 10, "candidatesTokenCount": 5, "totalTokenCount": 15}


def test_empty_usage_chunk_accepted_then_dimensions_accumulated():
    decoder = adapter().create_stream_decoder(logical_model="logical")
    assert decoder.feed(stream(chunk("synthetic", {}))) is not None
    assert decoder.usage == (None, None)
    events = decoder.feed(stream(chunk("synthetic", valid_usage(), finish="STOP")))
    assert decoder.usage == (10, 5)
    wire = b"".join(events + decoder.finish())
    assert b"response.completed" in wire


def test_partial_usage_chunk_still_rejected():
    decoder = adapter().create_stream_decoder(logical_model="logical")
    with pytest.raises(ValueError, match="Invalid native usage dimensions"):
        decoder.feed(stream(chunk("synthetic", {"promptTokenCount": 10})))
    assert decoder.usage_invalid is True
    assert decoder.usage == (None, None)


def test_malformed_usage_after_empty_chunk_still_rejected():
    decoder = adapter().create_stream_decoder(logical_model="logical")
    decoder.feed(stream(chunk("synthetic", {})))
    with pytest.raises(ValueError, match="Invalid native usage dimensions"):
        decoder.feed(stream(chunk("synthetic", {"promptTokenCount": "x"}, finish="STOP")))
    assert decoder.usage_invalid is True


def test_usage_decrease_after_empty_chunk_still_rejected():
    decoder = adapter().create_stream_decoder(logical_model="logical")
    decoder.feed(stream(chunk("synthetic", {})))
    decoder.feed(stream(chunk("synthetic", valid_usage())))
    with pytest.raises(ValueError, match="Native cumulative usage decreased"):
        decoder.feed(
            stream(
                chunk(
                    "synthetic",
                    {
                        "promptTokenCount": 10,
                        "candidatesTokenCount": 3,
                        "totalTokenCount": 13,
                    },
                )
            )
        )


def test_stream_without_usage_completes_with_unknown_usage():
    decoder = adapter().create_stream_decoder(logical_model="logical")
    payload = {
        "candidates": [
            {"content": {"role": "model", "parts": [{"text": "synthetic"}]}, "finishReason": "STOP"}
        ]
    }
    wire = b"".join(decoder.feed(stream(payload)) + decoder.finish())
    assert b"response.completed" in wire
    assert decoder.usage == (None, None)
