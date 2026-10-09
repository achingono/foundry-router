"""One-time atomic historical quota bootstrap before a canary app exists."""

import hashlib
import json
from contextlib import suppress
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from foundry_router.ratelimit import QuotaStoreError
from foundry_router.state.quota import ROW_KEY, AzureTableRateLimitStore, _partition
from foundry_router.state.table import _TransactionEntity

MAX_DAILY = 20
SHA_LENGTH = 64

MARKER = "canary-bootstrap-v1"


async def bootstrap(client, settings, *, counts, history_sha256, now=None):  # noqa: PLR0912 -- one atomic bootstrap gate
    """Create marker and seeded counter in the same transaction; never replay history."""
    now = now or datetime.now(UTC)
    day = now.astimezone(ZoneInfo("America/Los_Angeles")).date().isoformat()
    if set(counts) != set(settings.quota_group_rate_limits):
        raise ValueError("Bootstrap groups mismatch")
    if any(type(value) is not int or not 0 <= value <= MAX_DAILY for value in counts.values()):
        raise ValueError("Bootstrap count out of bounds")
    if len(history_sha256) != SHA_LENGTH or any(
        c not in "0123456789abcdef" for c in history_sha256
    ):
        raise ValueError("Bootstrap history digest invalid")
    store = AzureTableRateLimitStore(client, now_fn=lambda: now)
    # Only initialize groups without a marker. Existing markers are never overwritten,
    # including after midnight; normal quota accounting owns rollover.
    await store.sync_from_settings(settings)
    for group, count in counts.items():
        expected = {"history_sha256": history_sha256, "seed_day": day, "seed_count": count}
        for _ in range(8):
            marker = await client.get_entity(_partition(group), MARKER)
            if marker is not None:
                if (
                    marker.get("history_sha256") != history_sha256
                    or marker.get("seed_count") != count
                ):
                    raise QuotaStoreError("Bootstrap history mismatch")
                state_entity = await client.get_entity(_partition(group), ROW_KEY)
                if state_entity is None:
                    raise QuotaStoreError("Bootstrap state missing")
                state = store._decode(group, state_entity)
                seed_day = marker.get("seed_day")
                if seed_day in state["daily"] and state["daily"][seed_day] < count:
                    raise QuotaStoreError("Bootstrap counter regressed")
                if state["day"] < seed_day:
                    raise QuotaStoreError("Bootstrap date regressed")
                break
            if store._boundary(now.timestamp()):
                raise QuotaStoreError("Bootstrap denied near Pacific rollover")
            entity = await client.get_entity(_partition(group), ROW_KEY)
            if entity is None:
                raise QuotaStoreError("Bootstrap state unavailable")
            state = store._decode(group, entity)
            if state["records"] or any(state["daily"].values()):
                raise QuotaStoreError("Bootstrap requires unused state")
            state["daily"] = {day: count}
            state["day"] = day
            transaction = [
                _TransactionEntity(
                    _partition(group),
                    ROW_KEY,
                    "Update",
                    store._entity(group, state),
                    entity["odata.etag"],
                ),
                _TransactionEntity(
                    _partition(group),
                    MARKER,
                    "Create",
                    {"PartitionKey": _partition(group), "RowKey": MARKER, **expected},
                ),
            ]
            # Acknowledgment may be lost after commit. Resolve by marker read.
            with suppress(TimeoutError, OSError):
                await client.try_batch_transaction(transaction)
        else:
            raise QuotaStoreError("Bootstrap contention exhausted")
    return store


def history_digest(paths):
    return hashlib.sha256(
        json.dumps(
            [(str(p), hashlib.sha256(p.read_bytes()).hexdigest()) for p in paths], sort_keys=True
        ).encode()
    ).hexdigest()
