"""Bounded inclusive synchronous timing facts for isolated synthetic measurements."""

from __future__ import annotations

import asyncio
import functools
import sys
import threading
import time
from contextlib import ExitStack
from unittest.mock import patch

import httpx._content as content

from foundry_router.api import google_state
from foundry_router.api.adapters.google_signed import GoogleSignedAdapter
from foundry_router.api.google_sealing import SealContext
from foundry_router.api.google_work import SignedWorkLease
from foundry_router.credit import estimate_request_cost


class StageProfile:
    def __init__(self):
        self.main_thread = threading.get_ident()
        self.lock = threading.Lock()
        self.rows = {}
        self.patches = ExitStack()

    def wrap(self, name, function):
        @functools.wraps(function)
        def measure(*args, **kwargs):
            start = time.monotonic()
            on_main = threading.get_ident() == self.main_thread
            try:
                return function(*args, **kwargs)
            finally:
                elapsed = (time.monotonic() - start) * 1000
                key = name + (".main" if on_main else ".worker")
                with self.lock:
                    row = self.rows.setdefault(key, {"count": 0, "max_ms": 0, "total_ms": 0})
                    row["count"] += 1
                    row["max_ms"] = max(row["max_ms"], elapsed)
                    row["total_ms"] += elapsed

        return measure

    def start(self):
        bindings = {
            "canonical_bytes": google_state.canonical_bytes,
            "framed_digest": google_state.framed_digest,
            "estimate_request_cost": estimate_request_cost,
        }
        # Imported bindings retain function identity; patch all repository aliases.
        for module_name, module in list(sys.modules.items()):
            if not module_name.startswith("foundry_router") or module is None:
                continue
            for name, function in bindings.items():
                if getattr(module, name, None) is function:
                    self.patches.enter_context(
                        patch.object(module, name, self.wrap(name, function))
                    )
        for owner, names in [
            (GoogleSignedAdapter, ("check_request", "build_upstream_body")),
            (SealContext, ("validate", "validate_dispatch")),
        ]:
            for name in names:
                self.patches.enter_context(
                    patch.object(owner, name, self.wrap(name, getattr(owner, name)))
                )

        self.patches.enter_context(
            patch.object(
                content, "encode_json", self.wrap("httpx_encode_json", content.encode_json)
            )
        )

    def close(self):
        self.patches.close()

    def facts(self):
        with self.lock:
            return {
                "scope": "inclusive nested synchronous wall timings; totals overlap; no CPU sum",
                "stages": {name: dict(row) for name, row in self.rows.items()},
            }


async def drain_signed_capacity(timeout_seconds=2):
    """Wait finitely for shielded signed jobs; never release another owner's lease."""
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        leases = []
        try:
            leases.append(SignedWorkLease())
            leases.append(SignedWorkLease())
        except ValueError:
            pass
        else:
            return True
        finally:
            for lease in leases:
                lease.close()
        await asyncio.sleep(0.01)
    return False
