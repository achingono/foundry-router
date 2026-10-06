"""Synthetic profiling facts and bounded shielded-capacity drain semantics."""

import asyncio
import importlib.util
from pathlib import Path

import pytest

from foundry_router.api.google_work import SignedWorkLease

SPEC = importlib.util.spec_from_file_location(
    "resource_profile",
    Path(__file__).resolve().parents[2] / "scripts/quality/google_resource_profile.py",
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_profile_preserves_return_and_exception_without_content():
    profile = MODULE.StageProfile()
    assert profile.wrap("owned", lambda: "PRIVATE_CONTENT")() == "PRIVATE_CONTENT"
    with pytest.raises(ValueError):
        profile.wrap("failure", lambda: (_ for _ in ()).throw(ValueError("PRIVATE_ERROR")))()
    facts = profile.facts()
    assert facts["stages"]["owned.main"]["count"] == 1
    assert facts["stages"]["failure.main"]["count"] == 1
    assert "PRIVATE" not in str(facts)


async def test_drain_waits_for_owner_without_stealing_slot():
    lease = SignedWorkLease()
    lease.start()
    lease.close()
    task = asyncio.create_task(MODULE.drain_signed_capacity(0.5))
    await asyncio.sleep(0.02)
    assert not task.done()
    lease.finish()
    assert await task


async def test_drain_timeout_does_not_release_active_owner():
    lease = SignedWorkLease()
    lease.start()
    lease.close()
    try:
        assert not await MODULE.drain_signed_capacity(0.02)
        replacement = SignedWorkLease()
        try:
            with pytest.raises(ValueError, match="busy"):
                SignedWorkLease()
        finally:
            replacement.close()
    finally:
        lease.finish()
    assert await MODULE.drain_signed_capacity(0.02)
