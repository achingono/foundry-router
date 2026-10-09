"""Exact opaque signatures may be omitted only from stateless Google text output."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from foundry_router.api.adapters.compatible_text import CompatibleTextAdapter
from foundry_router.api.adapters.google_ai_studio import GoogleAiStudioAdapter, GoogleStreamDecoder
from tests.unit.test_google_compatible_verification import chat, stream_wire


def signed():
    data = chat()
    data["choices"][0]["message"]["extra_content"] = {
        "google": {"thought_signature": "opaque-signature"}
    }
    return data


def test_nonstream_exact_signature_omitted_without_mutation():
    adapter = GoogleAiStudioAdapter()
    data = signed()
    result = adapter.translate_success(
        "responses", data, logical_model="m", request_body={"input": "hello"}
    )
    assert (
        result.body["status"] == "completed"
        and result.input_tokens == 10
        and result.output_tokens == 2
    )
    assert "opaque-signature" not in json.dumps(result.body)
    assert (
        data["choices"][0]["message"]["extra_content"]["google"]["thought_signature"]
        == "opaque-signature"
    )


@pytest.mark.parametrize(
    "value",
    [
        {"google": {"thought_signature": 42}},
        {"google": {"thought_signature": ""}},
        {"google": {"thought_signature": "x" * 65537}},
        {"google": {"thought_signature": "private\nstate"}},
        {"google": {"thought_signature": "\ud800"}},
        {"google": {"thought_signature": "signature", "unknown": "state"}},
        {"gemini": {"thought_signature": "state"}},
        [],
    ],
)
def test_malformed_unknown_and_oversize_state_rejected(value):
    data = signed()
    data["choices"][0]["message"]["extra_content"] = value
    with pytest.raises(ValueError):
        GoogleAiStudioAdapter().translate_success(
            "responses", data, logical_model="m", request_body={"input": "hello"}
        )


def test_generic_provider_retains_strict_state_rejection():
    with pytest.raises(ValueError):
        CompatibleTextAdapter().translate_success(
            "responses", signed(), logical_model="m", request_body={"input": "hello"}
        )


@pytest.mark.parametrize(
    "body",
    [
        {"input": "hello", "tools": []},
        {"input": "hello", "text": {"format": {"type": "text"}}},
        {"input": "hello", "previous_response_id": "previous"},
        {"input": "hello", "google_state": "state"},
        {"input": "hello", "store": True},
    ],
)
def test_ineligible_requests_do_not_normalize(body):
    adapter = GoogleAiStudioAdapter()
    assert not adapter.request_context(body).stateless_signature_text
    with pytest.raises(ValueError):
        adapter.translate_success("responses", signed(), logical_model="m", request_body=body)


@pytest.mark.parametrize("inert", [None, {}])
def test_inert_extra_content_only_for_eligible_text(inert):
    data = signed()
    data["choices"][0]["message"]["extra_content"] = inert
    assert (
        GoogleAiStudioAdapter()
        .translate_success("responses", data, logical_model="m", request_body={"input": "hello"})
        .body["status"]
        == "completed"
    )


def test_fragmented_sse_wire_signature_delta_preserves_text_usage():
    adapter = GoogleAiStudioAdapter()
    decoder = adapter.create_stream_decoder(logical_model="m", request_body={"input": "hello"})
    data = chat()
    wire = stream_wire(data)
    # Signature arrives as a final metadata-only delta before terminal completion.
    signature = (
        b"data: "
        + json.dumps(
            {
                "choices": [
                    {
                        "index": 0,
                        "delta": {
                            "extra_content": {"google": {"thought_signature": "opaque-signature"}}
                        },
                        "finish_reason": None,
                    }
                ]
            }
        ).encode()
        + b"\n\n"
    )
    wire = wire.replace(b"data: [DONE]", signature + b"data: [DONE]")
    output = []
    for byte in wire:
        output.extend(decoder.feed(bytes([byte])))
    output.extend(decoder.finish())
    assert decoder.validated and decoder.usage == (10, 2)
    joined = b"".join(output)
    assert (
        b"opaque-signature" not in joined and b"response.completed" in joined and b"ready" in joined
    )


def test_decoder_request_policy_is_copied_and_ineligible_context_rejects():
    adapter = GoogleAiStudioAdapter()
    context = replace(adapter.request_context({"input": "hello"}), stateless_signature_text=False)
    decoder = GoogleStreamDecoder(logical_model="m", context=context)
    wire = (
        b"data: "
        + json.dumps(
            {
                "choices": [
                    {
                        "delta": {"extra_content": {"google": {"thought_signature": "private"}}},
                        "finish_reason": None,
                    }
                ]
            }
        ).encode()
        + b"\n\n"
    )
    with pytest.raises(ValueError):
        decoder.feed(wire)


def test_nonempty_other_state_still_rejected():
    data = signed()
    data["choices"][0]["message"]["reasoning_content"] = "private reasoning"
    with pytest.raises(ValueError):
        GoogleAiStudioAdapter().translate_success(
            "responses", data, logical_model="m", request_body={"input": "hello"}
        )


def test_new_acceptance_cases_preserve_previous_failure_prefix(tmp_path):
    import httpx
    from google_compatible_stage import execute_stage
    from google_signature_acceptance import CASES, DIRECTORY

    baseline = json.loads((DIRECTORY / "ledger-baseline.json").read_text())
    (tmp_path / "ledger-baseline.json").write_text(json.dumps(baseline))
    ledger = tmp_path / "ledger.json"
    ledger.write_text(json.dumps(baseline))
    calls = []

    def handle(request):
        calls.append(request)
        data = signed()
        if json.loads(request.content).get("stream"):
            wire = stream_wire(chat())
            signature = (
                b"data: "
                + json.dumps(
                    {
                        "choices": [
                            {
                                "delta": {
                                    "extra_content": {"google": {"thought_signature": "opaque"}}
                                },
                                "finish_reason": None,
                            }
                        ]
                    }
                ).encode()
                + b"\n\n"
            )
            return httpx.Response(
                200,
                content=wire.replace(b"data: [DONE]", signature + b"data: [DONE]"),
                headers={"content-type": "text/event-stream"},
            )
        return httpx.Response(200, json=data)

    result = execute_stage(
        "unused",
        stage_dir=tmp_path,
        ledger_path=ledger,
        credentials=["synthetic"] * 5,
        transport_factory=lambda: httpx.MockTransport(handle),
        cases=CASES,
    )
    assert len(calls) == 8 and all(case["status"] == "passed" for case in result["attempts"])
    updated = json.loads(ledger.read_text())
    assert updated["projects"]["project-1"] == baseline["projects"]["project-1"]
    for project, old in baseline["projects"].items():
        assert all(
            updated["projects"][project]["cases"][case] == debit
            for case, debit in old["cases"].items()
        )
    execute_stage(
        "unused",
        stage_dir=tmp_path,
        ledger_path=ledger,
        credentials=["synthetic"] * 5,
        transport_factory=lambda: httpx.MockTransport(handle),
        cases=CASES,
    )
    assert len(calls) == 8
