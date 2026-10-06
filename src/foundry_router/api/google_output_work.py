"""Two request-owned generated-output inspection slots with bounded child cleanup."""

from __future__ import annotations

import asyncio
import hashlib
import math
import struct
import sys
import threading
import zlib
from contextlib import suppress
from dataclasses import dataclass

from foundry_router.api.adapters.google_schema import load_bounded_json
from foundry_router.api.google_output_png import MAX_PNG_BYTES

_SLOTS = threading.BoundedSemaphore(2)
_SLOT_LOCK = threading.Lock()
_WORKER_SECONDS = 2
_METADATA_BYTES = 1024


def _probe_png() -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 1024, 1024, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"\0" * 3146752))
        + chunk(b"IEND", b"")
    )


_PROBE_PNG = _probe_png()


@dataclass(frozen=True, repr=False)
class PreparedOutputPng:
    digest: str
    decoded_bytes: int
    expanded_bytes: int


class OutputInspectionLease:
    """Caller close retains a busy slot until the child is killed and reaped."""

    def __init__(self, *, slots: int = 1) -> None:
        if type(slots) is not int or slots not in (1, 2):
            raise ValueError("Invalid generated output capacity")
        with _SLOT_LOCK:
            for acquired in range(slots):
                if not _SLOTS.acquire(blocking=False):
                    for _ in range(acquired):
                        _SLOTS.release()
                    raise ValueError("Generated output inspection is busy")
        self._slots = slots
        self._closed = False
        self._active = False
        self._released = False
        self.delivery_deadline: float | None = None

    def bind_delivery_deadline(self, deadline: float) -> None:
        if type(deadline) not in (int, float) or not math.isfinite(deadline):
            raise ValueError("Invalid generated output delivery deadline")
        if self.delivery_deadline is not None and deadline != self.delivery_deadline:
            raise ValueError("Generated output delivery deadline cannot change")
        self.delivery_deadline = deadline

    def close(self) -> None:
        self._closed = True
        self._release()

    def _release(self) -> None:
        with _SLOT_LOCK:
            if self._closed and not self._active and not self._released:
                self._released = True
                for _ in range(self._slots):
                    _SLOTS.release()

    async def ready(self, *, deadline: float) -> bool:
        """Bounded actual worker probe using the same pre-admission request slot."""
        try:
            await self.inspect(_PROBE_PNG, deadline=deadline)
        except (ValueError, OSError, TimeoutError):
            return False
        return True

    async def inspect(self, raw: bytes, *, deadline: float) -> PreparedOutputPng:
        if self._closed or self._active or not 1 <= len(raw) <= MAX_PNG_BYTES:
            raise ValueError("Generated output inspection unavailable")
        if sys.platform != "linux":
            raise ValueError("Generated output inspector requires Linux")
        self._active = True
        work = self._inspect_owned(raw, deadline)
        try:
            task = asyncio.create_task(work)
        except BaseException:
            work.close()
            self._active = False
            self._release()
            raise
        # Consume an abandoned task failure; the task still owns child cleanup/capacity.
        task.add_done_callback(_observe_task)
        try:
            return await asyncio.shield(task)
        finally:
            # A failed Task retains its exception traceback, which includes this
            # awaiting frame. Remove the frame's Task/coroutine references so each
            # rejected near-limit artifact does not survive until cyclic GC.
            del task, work

    async def _inspect_owned(self, raw: bytes, deadline: float) -> PreparedOutputPng:
        process = None
        spawn = None
        try:
            async with asyncio.timeout_at(
                min(deadline, asyncio.get_running_loop().time() + _WORKER_SECONDS)
            ):
                spawn_work = asyncio.create_subprocess_exec(
                    sys.executable,
                    "-I",
                    "-m",
                    "foundry_router.api.google_output_png_worker",
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL,
                    limit=_METADATA_BYTES + 1,
                    env={"PATH": "", "PYTHONDONTWRITEBYTECODE": "1"},
                )
                try:
                    spawn = asyncio.create_task(spawn_work)
                except BaseException:
                    spawn_work.close()
                    raise
                process = await asyncio.shield(spawn)
                if process.stdin is None or process.stdout is None:
                    raise ValueError("Generated inspector pipes unavailable")
                process.stdin.write(raw)
                await process.stdin.drain()
                process.stdin.close()
                await process.stdin.wait_closed()
                metadata = bytearray()
                while len(metadata) <= _METADATA_BYTES:
                    piece = await process.stdout.read(_METADATA_BYTES + 1 - len(metadata))
                    if not piece:
                        break
                    metadata.extend(piece)
                if len(metadata) > _METADATA_BYTES or await process.wait() != 0:
                    raise ValueError("Generated PNG failed bounded inspection")
                facts = load_bounded_json(metadata.decode(), max_bytes=_METADATA_BYTES)
                if (
                    not isinstance(facts, dict)
                    or set(facts) != {"bytes", "width", "height", "expanded_bytes"}
                    or any(type(value) is not int for value in facts.values())
                    or facts["bytes"] != len(raw)
                    or facts["width"] != 1024
                    or facts["height"] != 1024
                    or type(facts["expanded_bytes"]) is not int
                    or facts["expanded_bytes"] not in (3146752, 4195328)
                ):
                    raise ValueError("Invalid generated inspector metadata")
                return PreparedOutputPng(
                    hashlib.sha256(raw).hexdigest(), len(raw), facts["expanded_bytes"]
                )
        finally:
            if process is None and spawn is not None:
                # Spawn is shielded: await it before releasing the child-owned slot.
                try:
                    process = await spawn
                except (OSError, asyncio.CancelledError):
                    process = None
            if process is not None:
                if process.returncode is None:
                    with suppress(ProcessLookupError):
                        process.kill()
                await process.wait()
            self._active = False
            self._release()


def _observe_task(task: asyncio.Task[PreparedOutputPng]) -> None:
    if not task.cancelled():
        task.exception()
