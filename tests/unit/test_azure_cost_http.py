"""Billing header diagnosis preserves normal rejection without exposing error bodies."""

import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/quality"))
import azure_cost_diagnostic as diagnostic
import azure_cost_http as observer

from foundry_router.reconciliation.azure_cost import AzureCostManagementProvider
from foundry_router.reconciliation.cost_types import CostEvidenceError
from tests.unit.test_azure_cost_reconciliation import RESOURCE, Credential, settings


@pytest.mark.parametrize(
    "values,kind,seconds",
    [
        ([], "absent", None),
        (["0"], "seconds", 0),
        (["86400"], "seconds", 86400),
        (["86401"], "invalid", None),
        (["0000000"], "invalid", None),
        ([" 12"], "invalid", None),
        (["-1"], "invalid", None),
        (["1.2"], "invalid", None),
        (["private-body"], "invalid", None),
        (["12", "12"], "invalid", None),
        (["\uff11\uff12"], "invalid", None),
        (["12, 15"], "invalid", None),
    ],
)
def test_retry_after_strict_bounded_headers(values, kind, seconds):
    result = observer.retry_after(
        httpx.Headers([(b"retry-after", value.encode("utf-8")) for value in values])
    )
    assert result == {"retry_after": kind, "retry_after_seconds": seconds}
    assert "private" not in json.dumps(result)


def record(**kwargs):
    return {
        "group": "account",
        "page": 1,
        "status": 429,
        "retry_after": "absent",
        "retry_after_seconds": None,
        **kwargs,
    }


@pytest.mark.parametrize(
    "mutation",
    [
        {"status": True},
        {"status": 999},
        {"page": 2},
        {"page": True},
        {"group": "private"},
        {"reason": "private"},
        {"retry_after": "private"},
        {"retry_after_seconds": 12},
        {"retry_after": "seconds", "retry_after_seconds": True},
    ],
)
def test_untrusted_record_fields_rejected(mutation):
    with pytest.raises(ValueError):
        observer.validate_records([record(**mutation)], ["account"])


class UntouchedStream(httpx.AsyncByteStream):
    read = False
    closed = False

    async def __aiter__(self):
        self.read = True
        yield b"private-error-body"

    async def aclose(self):
        self.closed = True


@pytest.mark.asyncio
async def test_http_rejection_records_headers_without_body_read_or_more_queries():
    stream = UntouchedStream()
    calls, records = [], []
    config = settings()
    # A later configured group must never run after this rejection.
    config.cost_management_groups["second"] = config.cost_management_groups["account"]
    from foundry_router.config.cost_management import CostGroupConfig

    config.cost_management_groups["second"] = CostGroupConfig(
        scope=config.cost_management_groups["account"].scope, resource_ids=(RESOURCE + "second",)
    )
    config.backend_cycle_start_day["second"] = 1
    config.backend_cycle_allowance_usd["second"] = 100

    def reject(request):
        calls.append(request)
        return httpx.Response(
            429, headers={"retry-after": "17", "private": "private-header"}, stream=stream
        )

    inner = httpx.MockTransport(reject)
    transport = observer.HeaderTransport(config, records, inner)
    provider = AzureCostManagementProvider(credential=Credential(), transport=transport)
    try:
        with pytest.raises(CostEvidenceError, match="cost_http_unavailable"):
            await provider.fetch_remaining_credit(config)
    finally:
        await provider.close()
    assert len(calls) == 1 and not stream.read and stream.closed
    assert records == [record(retry_after="seconds", retry_after_seconds=17)]
    observer.validate_records(records, config.cost_management_groups)
    assert "private" not in json.dumps(records)


@pytest.mark.asyncio
@pytest.mark.parametrize("values", [[RESOURCE + "wrong"], [RESOURCE, RESOURCE], [None], []])
async def test_binding_rejected_before_transport(values):
    calls = []
    transport = observer.HeaderTransport(settings(), [], httpx.MockTransport(calls.append))
    request = httpx.Request(
        "POST",
        "https://management.azure.com/synthetic",
        json={"dataset": {"filter": {"dimensions": {"values": values}}}},
    )
    try:
        with pytest.raises(ValueError):
            await transport.handle_async_request(request)
        assert not calls
    finally:
        await transport.aclose()


def test_consumed_http_invocation_refuses_external_replay(tmp_path):
    calls = []

    async def verify(_settings):
        calls.append(True)
        raise CostEvidenceError("cost_http_unavailable")

    result = diagnostic.execute(
        directory=tmp_path,
        prepare=settings,
        verify=verify,
        finalize=lambda result: {**result, "http_observations": [record()]},
    )
    assert result["status"] == "unverified" and len(calls) == 1
    with pytest.raises(ValueError):
        diagnostic.execute(directory=tmp_path, prepare=lambda: calls.append(True), verify=verify)
    assert len(calls) == 1
