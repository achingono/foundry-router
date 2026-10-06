"""Attribution harness retains owned workers and restores patches through cancellation."""

import asyncio
import importlib.util
import threading
from pathlib import Path

import pytest

from foundry_router.api import google_state

ROOT = Path(__file__).resolve().parents[2]


async def test_repeated_cancel_waits_for_harness_worker_and_restores_profile(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts/quality"))
    spec = importlib.util.spec_from_file_location(
        "resource_attribution", ROOT / "scripts/quality/google_signed_resource.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module.rss_helpers, "aggregate_rss", lambda: 0)
    entered = asyncio.Event()
    loop = asyncio.get_running_loop()
    release = threading.Event()
    original_decode = module.json.loads
    original_canonical = google_state.canonical_bytes

    def blocked_decode(value, *args, **kwargs):
        if isinstance(value, bytes) and b'"contents"' in value:
            loop.call_soon_threadsafe(entered.set)
            release.wait(3)
        return original_decode(value, *args, **kwargs)

    monkeypatch.setattr(module.json, "loads", blocked_decode)
    task = asyncio.create_task(module.run(callers=1, attempts=2, preencoded=True, profile=True))
    try:
        await asyncio.wait_for(entered.wait(), 2)
        task.cancel()
        await asyncio.sleep(0.01)
        task.cancel()
        await asyncio.sleep(0.01)
        assert not task.done()
    finally:
        release.set()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, 2)
    assert google_state.canonical_bytes is original_canonical
    from foundry_router.api.google_work import SignedWorkLease

    leases = [SignedWorkLease(), SignedWorkLease()]
    for lease in leases:
        lease.close()
