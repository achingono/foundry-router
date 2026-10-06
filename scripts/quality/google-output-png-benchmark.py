"""Synthetic Linux output-inspector capacity/resource checks; no provider credentials."""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import struct
import time
import zlib
from pathlib import Path

from foundry_router.api.google_output_work import OutputInspectionLease

LAST_ROW = 1023

CALLERS = 8
ATTEMPTS = 100


def chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


def fixture(invalid=False, exact=False):
    randomizer = random.Random(1)
    pixels = randomizer.randbytes(972 * 1024)
    rows = []
    for index in range(1024):
        rows.append(  # noqa: PERF401 -- readable finite binary fixture
            bytes([5 if invalid and index == LAST_ROW else 0])
            + pixels[index * 972 : (index + 1) * 972]
            + b"\0" * (4096 - 972)
        )
    raster = b"".join(rows)
    payload = zlib.compress(raster, 1)
    if exact:
        # Insert only zero-length stored DEFLATE blocks at a sync boundary.
        # No metadata, raster expansion or second stream changes the contract.
        for split in range(1, 100):
            compressor = zlib.compressobj(1)
            head = compressor.compress(raster[:split]) + compressor.flush(zlib.Z_SYNC_FLUSH)
            tail = compressor.compress(raster[split:]) + compressor.flush()
            remaining = 1048576 - 57 - len(head) - len(tail)
            if remaining >= 0 and remaining % 5 == 0:
                payload = head + b"\0\0\0\xff\xff" * (remaining // 5) + tail
                break
        else:
            raise ValueError("Exact output fixture cannot be constructed")
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 1024, 1024, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", payload)
        + chunk(b"IEND", b"")
    )


def container_peak():
    for name in ("/sys/fs/cgroup/memory.peak", "/sys/fs/cgroup/memory/memory.max_usage_in_bytes"):
        path = Path(name)
        if path.exists():
            return int(path.read_text())
    return None


def aggregate_rss():
    total = 0
    for directory in Path("/proc").iterdir():
        if not directory.name.isdigit():
            continue
        try:
            lines = (directory / "status").read_text().splitlines()
        except (FileNotFoundError, ProcessLookupError):
            continue
        for line in lines:
            if line.startswith("VmRSS:"):
                total += int(line.split()[1]) * 1024
    return total


async def run(invalid):
    raw = fixture(invalid)
    baseline = aggregate_rss()
    peak = baseline
    active = True
    delays = []
    statuses = {}
    latencies = []

    async def monitor():
        nonlocal peak
        while active:
            start = time.monotonic()
            await asyncio.sleep(0.005)
            delays.append(max(0, time.monotonic() - start - 0.005))
            peak = max(peak, aggregate_rss())

    async def caller():
        for _ in range(ATTEMPTS):
            start = time.monotonic()
            try:
                lease = OutputInspectionLease()
            except ValueError:
                outcome = "busy"
            else:
                try:
                    # Synthetic provider wait demonstrates slot ownership before output arrives.
                    await asyncio.sleep(0.005)
                    await lease.inspect(raw, deadline=time.monotonic() + 2)
                    outcome = "valid"
                except ValueError:
                    outcome = "invalid"
                finally:
                    lease.close()
            statuses[outcome] = statuses.get(outcome, 0) + 1
            latencies.append(time.monotonic() - start)
            await asyncio.sleep(0.001)

    watcher = asyncio.create_task(monitor())
    start = time.monotonic()
    try:
        async with asyncio.timeout(60):
            await asyncio.gather(*(caller() for _ in range(CALLERS)))
    finally:
        active = False
        await watcher
    return {
        "synthetic_only": True,
        "workload": "late-invalid" if invalid else "maximum",
        "png_decoded_bytes": len(raw),
        "expanded_bytes": 4195328,
        "callers": CALLERS,
        "attempts_per_caller": ATTEMPTS,
        "outcomes": statuses,
        "baseline_parent_children_rss": baseline,
        "sampled_peak_parent_children_rss": peak,
        "incremental_parent_children_rss": peak - baseline,
        "container_peak_bytes": await asyncio.to_thread(container_peak),
        "max_loop_delay_ms": max(delays) * 1000,
        "max_request_ms": max(latencies) * 1000,
        "wall_seconds": time.monotonic() - start,
        "network_disabled": True,
        "container_memory_bytes": 536870912,
        "container_cpus": 2,
        "scope": "direct output lease/real child with synthetic provider wait; no HTTP admission",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--invalid", action="store_true")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(args.invalid)), sort_keys=True))
