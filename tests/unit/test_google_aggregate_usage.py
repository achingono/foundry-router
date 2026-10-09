"""Google aggregate usage is conserved through Responses and settlement."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/quality"))
import google_compatible_runtime as runtime
import httpx
import pytest
from google_live_budget import BudgetLedger

from foundry_router.api.adapters.compatible_text import CompatibleTextAdapter
from foundry_router.api.adapters.google_ai_studio import (
    GoogleAiStudioAdapter,
    GoogleStreamDecoder,
    normalize_google_usage,
)
from tests.unit.test_google_compatible_verification import chat, stream_wire


@pytest.mark.parametrize("stream", [False, True])
async def test_aggregate_total_settles_through_actual_responses_route(tmp_path, stream):
    data = chat(7, 2)
    data["usage"]["total_tokens"] = 71
    original = json.dumps(data)
    result = await runtime.run_compatible_case(
        credential="synthetic",
        ledger=BudgetLedger(tmp_path / "ledger.json"),
        project="project-1",
        case_id="aggregate",
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200, content=stream_wire(data) if stream else json.dumps(data).encode()
            )
        ),
        stream=stream,
        model="gemini-3.8-flash",
    )
    assert (
        result["status"] == "passed"
        and result["input_tokens"] == 7
        and result["output_tokens"] == 64
    )
    assert result["actual_tokens"] == 71 and result["synthetic_debit_usd"] == 0.071
    assert result["reservations_cleared"] and json.dumps(data) == original


@pytest.mark.parametrize(
    "usage",
    [
        {"prompt_tokens": True, "completion_tokens": 2, "total_tokens": 3},
        {"prompt_tokens": 7, "completion_tokens": 2, "total_tokens": 8},
        {"prompt_tokens": 7, "completion_tokens": 2, "total_tokens": -1},
    ],
)
def test_malformed_usage_rejected(usage):
    with pytest.raises(ValueError):
        normalize_google_usage(usage)


def test_missing_completion_stays_unknown_and_generic_unchanged():
    assert (
        normalize_google_usage({"prompt_tokens": 7, "total_tokens": 71}).get("completion_tokens")
        is None
    )
    data = chat(7, 2)
    data["usage"]["total_tokens"] = 71
    assert (
        CompatibleTextAdapter()
        .translate_success("responses", data, logical_model="m")
        .output_tokens
        == 2
    )
    assert GoogleAiStudioAdapter().extract_usage(
        "embeddings", {"usage": {"prompt_tokens": 7, "total_tokens": 71}}
    ) == (7, 0)


@pytest.mark.parametrize(
    "snapshots,expected",
    [
        (
            [
                {"prompt_tokens": 7, "completion_tokens": 2, "total_tokens": 71},
                {"prompt_tokens": 7, "total_tokens": 71},
            ],
            (7, None),
        ),
        (
            [
                {"prompt_tokens": 7, "total_tokens": 71},
                {"prompt_tokens": 7, "completion_tokens": 2, "total_tokens": 71},
            ],
            (7, 64),
        ),
    ],
)
def test_stream_snapshot_replaces_dimensions(snapshots, expected):
    decoder = GoogleStreamDecoder(logical_model="m")
    for usage in snapshots:
        decoder._absorb_usage(usage)
    assert decoder.usage == expected


def test_decreasing_complete_snapshot_clears_known_usage():
    decoder = GoogleStreamDecoder(logical_model="m")
    decoder._absorb_usage({"prompt_tokens": 7, "completion_tokens": 2, "total_tokens": 71})
    with pytest.raises(ValueError):
        decoder._absorb_usage({"prompt_tokens": 7, "completion_tokens": 2, "total_tokens": 70})
    assert decoder.usage == (None, None)


@pytest.mark.parametrize("complete_last", [False, True])
async def test_actual_route_requires_complete_final_usage_snapshot(tmp_path, complete_last):
    complete = {"prompt_tokens": 7, "completion_tokens": 2, "total_tokens": 71}
    partial = {"prompt_tokens": 7, "total_tokens": 71}
    wire = stream_wire(chat(7, 2))
    # Replace the terminal usage frame with two ordered snapshots.
    marker = (
        "data: "
        + json.dumps({"id": "chatcmpl-synthetic", "choices": [], "usage": chat(7, 2)["usage"]})
        + "\n\n"
    ).encode()
    frames = b"".join(
        (
            "data: " + json.dumps({"id": "chatcmpl-synthetic", "choices": [], "usage": u}) + "\n\n"
        ).encode()
        for u in ([partial, complete] if complete_last else [complete, partial])
    )
    assert marker in wire
    wire = wire.replace(marker, frames)
    result = await runtime.run_compatible_case(
        credential="synthetic",
        ledger=BudgetLedger(tmp_path / "ledger.json"),
        project="project-1",
        case_id="snapshots",
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, content=wire)),
        stream=True,
        model="gemini-3.8-flash",
    )
    assert result["reservations_cleared"]
    assert result["status"] == ("passed" if complete_last else "failed")
    assert result["synthetic_debit_usd"] == (0.071 if complete_last else 1.033)
