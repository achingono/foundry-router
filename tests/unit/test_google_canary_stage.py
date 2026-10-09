"""Actual TCP canary route verifies complete nonstream usage without SSE mirror."""

import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/quality"))
from google_canary_stage import MODEL, AggregateNonstream, retry_allowed
from google_stream_runtime import run_case

from tests.unit.test_google_compatible_verification import chat


async def test_nonstream_aggregate_actual_tcp_route():
    data = chat(7, 2)
    data["usage"]["total_tokens"] = 71
    dispatches = []
    result = await run_case(
        credential="synthetic",
        case={
            "case_id": "test-canary",
            "project": "project-3",
            "prompt": "ordinary",
            "stream": False,
            "cancel": False,
        },
        model=MODEL,
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=data)),
        reserve=lambda: dispatches.append(True),
        progress=lambda _: None,
        observer=AggregateNonstream(),
    )
    assert result["status"] == "passed" and len(dispatches) == 1
    assert result["actual_tokens"] == 71 and result["settlement_matches"]


def test_retry_requires_provider_status_and_clean_accounting():
    valid = {
        "provider_http_status": 503,
        "http_status": 503,
        "natural_cleanup": True,
        "settlement_matches": True,
        "budget_overrun": False,
    }
    assert retry_allowed(valid)
    assert not retry_allowed({**valid, "provider_http_status": 200, "http_status": 502})
    assert not retry_allowed({**valid, "natural_cleanup": False})
    assert not retry_allowed({**valid, "settlement_matches": False})
    assert not retry_allowed({**valid, "budget_overrun": True})
