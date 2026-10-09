"""Diagnostic failures expose fixed categories; starts are durable and never replayed."""

import json
import sys
from pathlib import Path

import pytest
from azure.core.exceptions import ClientAuthenticationError

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/quality"))
import azure_cost_diagnostic as diagnostic

from foundry_router.reconciliation.cost_types import CostEvidenceError


@pytest.mark.parametrize(
    "error,expected",
    [
        (CostEvidenceError("cost_http_unavailable"), "http_rejection"),
        (CostEvidenceError("cost_rows_unavailable"), "schema"),
        (CostEvidenceError("secret-state"), "unknown"),
        (ValueError("private-value"), "unknown"),
        (ClientAuthenticationError("private-identity"), "identity"),
    ],
)
def test_category_never_exposes_exception(error, expected):
    assert diagnostic.category(error) == expected


def test_started_marker_blocks_repeated_refresh(tmp_path):
    calls = []

    async def verify(settings):
        calls.append(settings)
        raise CostEvidenceError("cost_columns_invalid")

    result = diagnostic.execute(directory=tmp_path, prepare=lambda: "synthetic", verify=verify)
    assert result["failure_boundary"] == "provider" and result["error_category"] == "schema"
    assert result["balance_applied"] is False and len(calls) == 1
    with pytest.raises(ValueError):
        diagnostic.execute(directory=tmp_path, prepare=lambda: "synthetic", verify=verify)
    assert len(calls) == 1


def test_interrupted_started_marker_refuses_without_external_calls(tmp_path):
    (tmp_path / diagnostic.STARTED.name).write_text(json.dumps({"started": True}))
    calls = []
    with pytest.raises(ValueError):
        diagnostic.execute(directory=tmp_path, prepare=lambda: calls.append(True))
    assert not calls
