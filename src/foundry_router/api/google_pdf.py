"""API-owned PDF preparation and immutable facts passed before admission."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import importlib.metadata
import importlib.util
import json
import logging
import re
import sys
from contextlib import suppress
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from foundry_router.api.google_audio import PreparedAudio
    from foundry_router.api.google_video import PreparedVideo

_PREFIX = "data:application/pdf;base64,"
_MAX_BYTES = 65536
_MAX_TOTAL_BYTES = 131072
_MAX_DOCUMENTS = 4
_WORKER_SECONDS = 2
# Bounded best-effort child reap detached from request cancellation. A stalled
# spawn/wait must never hold inspection capacity or suppress cancellation: on
# expiry the child is killed and its single in-flight wait task is transferred
# to explicit orphan tracking. No second waiter is ever started. At
# _MAX_PDF_ORPHANS tracked children, further inspection is rejected until reaping
# catches up; already admitted inspections can still transfer their child.
_CLEANUP_SECONDS = 1.0
_MAX_PDF_ORPHANS = 8
_ORPHANED_PDF_CHILDREN: set[Any] = set()


def pdf_orphaned_children() -> int:
    """Return the count of explicitly tracked unreaped PDF inspector children."""
    return len(_ORPHANED_PDF_CHILDREN)


def _wait_confirmed(done: asyncio.Task[Any], child: Any) -> bool:
    """Task completion alone never confirms reaping: require success and exit."""
    if done.cancelled():
        return False
    if done.exception() is not None:
        return False
    return getattr(child, "returncode", None) is not None


def _track_orphan_wait(child: Any, wait_task: asyncio.Task[Any]) -> None:
    """Take ownership of an in-flight child-wait task as a tracked orphan.

    The wait task is never duplicated: this same task is the sole waiter, and
    tracking is cleared only after successful, confirmed reaping. A failed or
    cancelled wait stays retained against the admission limit with an
    actionable warning, so unconfirmed children can never silently reopen
    capacity. In-flight orphans are always tracked; the capacity bound is
    enforced at inspection admission so persistent failures fail closed
    instead of accumulating children.
    """
    _ORPHANED_PDF_CHILDREN.add(child)

    def _settle(done: asyncio.Task[Any]) -> None:
        if _wait_confirmed(done, child):
            _ORPHANED_PDF_CHILDREN.discard(child)
        else:
            _LOGGER.warning(
                "pdf_inspector_reap_unconfirmed returncode=%r orphans=%d limit=%d",
                getattr(child, "returncode", None),
                len(_ORPHANED_PDF_CHILDREN),
                _MAX_PDF_ORPHANS,
            )

    wait_task.add_done_callback(_settle)


def _settle_pdf_spawn(spawn: asyncio.Task[Any]) -> None:
    """Consume a detached spawn task; any late process becomes a tracked orphan."""
    try:
        child = spawn.result()
    except BaseException:
        return
    if child is None:
        return
    try:
        if child.returncode is None:
            with suppress(ProcessLookupError):
                child.kill()
    except Exception:
        return
    try:
        wait_task = asyncio.create_task(child.wait())
    except RuntimeError:
        return
    _track_orphan_wait(child, wait_task)


def _orphan_pdf_spawn(spawn: asyncio.Task[Any] | None) -> None:
    if spawn is None or spawn.done():
        if spawn is not None:
            _settle_pdf_spawn(spawn)
        return
    spawn.cancel()
    spawn.add_done_callback(_settle_pdf_spawn)


async def _bounded_pdf_reap(
    process: asyncio.subprocess.Process | Any | None,
    spawn: asyncio.Task[Any] | None,
) -> None:
    """Resolve, kill and reap a PDF inspector child within a fixed bound.

    Never suppresses caller cancellation: a CancelledError during cleanup
    transfers the single wait task to explicit tracking and propagates, so the
    request finishes promptly while reaping still completes exactly once.
    """
    child = process
    if child is None and spawn is not None:
        try:
            async with asyncio.timeout(_CLEANUP_SECONDS):
                child = await asyncio.shield(spawn)
        except (TimeoutError, OSError):
            _orphan_pdf_spawn(spawn)
            child = None
        except asyncio.CancelledError:
            _orphan_pdf_spawn(spawn)
            raise
        except Exception:
            child = None
    if child is None:
        return
    try:
        stdin = getattr(child, "stdin", None)
        if stdin is not None:
            stdin.close()
    except Exception:
        pass
    try:
        transport = getattr(getattr(child, "stdout", None), "_transport", None)
        if transport is not None:
            transport.close()
    except Exception:
        pass
    try:
        if child.returncode is None:
            with suppress(ProcessLookupError):
                child.kill()
    except Exception:
        pass
    try:
        wait_task = asyncio.create_task(child.wait())
    except RuntimeError:
        return
    try:
        async with asyncio.timeout(_CLEANUP_SECONDS):
            await asyncio.shield(wait_task)
    except TimeoutError:
        _track_orphan_wait(child, wait_task)
    except asyncio.CancelledError:
        _track_orphan_wait(child, wait_task)
        raise
    except (OSError, Exception):
        # A failed wait is still tracked until its confirmation callback runs,
        # so every child has exactly one owner from creation to reaping.
        if not wait_task.done():
            wait_task.cancel()
        _track_orphan_wait(child, wait_task)


@dataclass(frozen=True, repr=False)
class PreparedPdf:
    position: tuple[int, int]
    digest: str
    decoded_bytes: int
    pages: int


@dataclass(frozen=True, repr=False)
class PreparedGoogleMedia:
    pdfs: tuple[PreparedPdf, ...]
    audio: tuple[PreparedAudio, ...] = ()
    video: tuple[PreparedVideo, ...] = ()

    def validate(self, body: dict[str, Any], profile: Any) -> None:
        # Audio uses the shared media error type; defer import to avoid an import cycle.
        from foundry_router.api.google_audio import validate_prepared_audio  # noqa: PLC0415
        from foundry_router.api.google_video import validate_prepared_video  # noqa: PLC0415

        validate_prepared_audio(body, self.audio, profile)
        validate_prepared_video(body, self.video, profile)
        parts = pdf_parts(body)
        if len(parts) != len(self.pdfs) or len(parts) > profile.max_pdfs:
            raise ValueError("PDF preparation item mismatch")
        for (position, part), entry in zip(parts, self.pdfs, strict=True):
            _validate_part_shape(part)
            uri = part.get("file_data")
            if (
                not isinstance(uri, str)
                or position != entry.position
                or hashlib.sha256(uri.encode()).hexdigest() != entry.digest
                or entry.decoded_bytes > profile.max_pdf_bytes
            ):
                raise ValueError("PDF preparation identity mismatch")
        if (
            sum(item.decoded_bytes for item in self.pdfs) > profile.max_total_pdf_bytes
            or sum(item.pages for item in self.pdfs) > profile.max_pdf_pages
        ):
            raise ValueError("PDF preparation aggregate bounds exceeded")


class PdfPreparationError(ValueError):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code


def pdf_parts(body: dict[str, Any]) -> list[tuple[tuple[int, int], dict[str, Any]]]:
    result: list[tuple[tuple[int, int], dict[str, Any]]] = []
    history = body.get("input")
    if not isinstance(history, list):
        return result
    if len(history) > 256:
        raise PdfPreparationError(422, "PDF history bound exceeded")
    for index, item in enumerate(history):
        if not isinstance(item, dict) or not isinstance(item.get("content"), list):
            continue
        if len(item["content"]) > 64:
            raise PdfPreparationError(422, "PDF content bound exceeded")
        for part_index, part in enumerate(item["content"]):
            if (
                isinstance(part, dict)
                and part.get("type") == "input_file"
                and not (
                    isinstance(part.get("file_data"), str)
                    and part["file_data"].startswith(
                        ("data:audio/wav;base64,", "data:video/avi;base64,")
                    )
                )
            ):
                if item.get("role") != "user" or len(result) >= _MAX_DOCUMENTS:
                    raise PdfPreparationError(422, "Unsupported PDF input placement or count")
                result.append(((index, part_index), part))
    return result


def decode_pdf(part: dict[str, Any]) -> bytes:
    _validate_part_shape(part)
    uri = part["file_data"]
    try:
        data = base64.b64decode(uri[len(_PREFIX) :], validate=True)
    except ValueError as exc:
        raise PdfPreparationError(422, "Invalid inline PDF encoding") from exc
    if not 1 <= len(data) <= _MAX_BYTES or base64.b64encode(data).decode() != uri[len(_PREFIX) :]:
        raise PdfPreparationError(422, "Invalid bounded canonical PDF encoding")
    return data


def _validate_part_shape(part: dict[str, Any]) -> None:
    filename = part.get("filename")
    uri = part.get("file_data")
    if (
        set(part) != {"type", "filename", "file_data"}
        or not isinstance(filename, str)
        or not re.fullmatch(r"[A-Za-z0-9_.-]{1,60}\.pdf", filename)
        or not isinstance(uri, str)
        or not uri.startswith(_PREFIX)
        or len(uri) > len(_PREFIX) + 4 * ((_MAX_BYTES + 2) // 3)
    ):
        raise PdfPreparationError(422, "Unsupported bounded inline PDF")


def pdf_worker_available() -> bool:
    try:
        return (
            sys.platform == "linux"
            and importlib.util.find_spec("pypdf") is not None
            and importlib.metadata.version("pypdf") == "6.19.0"
        )
    except importlib.metadata.PackageNotFoundError:
        return False


class PdfPreparer:
    """No-queue process-local slots; children are always killed/reaped on failure."""

    def __init__(self) -> None:
        self.active = 0
        self.probe: asyncio.Task[bool] | None = None

    async def ready(self) -> bool:
        """Cache successful probes; retry transient failures on the next call.

        A single wedged or unavailable worker must not permanently poison
        readiness. Concurrent callers share one in-flight probe (single-flight);
        a completed ``False`` result or task failure is cleared so recovery is
        observed without a process restart. Successful probes stay cached.
        """
        if not pdf_worker_available():
            return False
        if self.probe is None:
            if self.active >= 2:
                return False
            self.active += 1
            self.probe = asyncio.create_task(self._probe())
        task = self.probe
        try:
            result = await asyncio.shield(task)
        except asyncio.CancelledError:
            raise
        except Exception:
            # Task failure (not a clean False) never poisons readiness.
            if self.probe is task:
                self.probe = None
            return False
        if result:
            return True
        # Transient False is not cached; next readiness check retries.
        if self.probe is task and task.done():
            self.probe = None
        return False

    async def _probe(self) -> bool:
        objects = [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Count 1 /Kids [3 0 R] >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 1 1] >>",
        ]
        data = bytearray(b"%PDF-1.4\n")
        offsets = []
        for index, body in enumerate(objects, 1):
            offsets.append(len(data))
            data.extend(f"{index} 0 obj\n".encode() + body + b"\nendobj\n")
        start = len(data)
        data.extend(b"xref\n0 4\n0000000000 65535 f \n")
        for offset in offsets:
            data.extend(f"{offset:010d} 00000 n \n".encode())
        data.extend(f"trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n".encode())
        try:
            return (
                await self.inspect(
                    bytes(data), deadline=asyncio.get_running_loop().time() + _WORKER_SECONDS
                )
                == 1
            )
        except PdfPreparationError:
            return False
        finally:
            self.active -= 1

    async def prepare(self, body: dict[str, Any], *, deadline: float) -> PreparedGoogleMedia | None:
        parts = pdf_parts(body)
        if not parts:
            return None
        if not pdf_worker_available():
            raise PdfPreparationError(503, "PDF inspector unavailable")
        if self.active >= 2:
            raise PdfPreparationError(503, "PDF inspector capacity unavailable")
        self.active += 1
        try:
            entries = []
            total = 0
            pages = 0
            for position, part in parts:
                digest = hashlib.sha256(str(part.get("file_data", "")).encode()).hexdigest()
                data = decode_pdf(part)
                total += len(data)
                if total > _MAX_TOTAL_BYTES:
                    raise PdfPreparationError(422, "PDF aggregate byte bound exceeded")
                count = await self.inspect(data, deadline=deadline)
                pages += count
                if pages > 4:
                    raise PdfPreparationError(422, "PDF aggregate page bound exceeded")
                entries.append(
                    PreparedPdf(
                        position,
                        digest,
                        len(data),
                        count,
                    )
                )
            return PreparedGoogleMedia(tuple(entries))
        finally:
            self.active -= 1

    async def inspect(self, data: bytes, *, deadline: float) -> int:
        if pdf_orphaned_children() >= _MAX_PDF_ORPHANS:
            raise PdfPreparationError(503, "PDF inspector unavailable")
        process: asyncio.subprocess.Process | None = None
        spawn: asyncio.Task[asyncio.subprocess.Process] | None = None
        try:
            async with asyncio.timeout_at(
                min(deadline, asyncio.get_running_loop().time() + _WORKER_SECONDS)
            ):
                spawn = asyncio.create_task(
                    asyncio.create_subprocess_exec(
                        sys.executable,
                        "-I",
                        "-m",
                        "foundry_router.api.google_pdf_worker",
                        stdin=asyncio.subprocess.PIPE,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.DEVNULL,
                        limit=1025,
                        env={"PATH": "", "PYTHONDONTWRITEBYTECODE": "1"},
                    )
                )
                process = await asyncio.shield(spawn)
                if process.stdin is None or process.stdout is None:
                    raise PdfPreparationError(503, "PDF inspector pipe unavailable")
                process.stdin.write(data)
                await process.stdin.drain()
                process.stdin.close()
                await process.stdin.wait_closed()
                raw = bytearray()
                while len(raw) <= 1024:
                    chunk = await process.stdout.read(1025 - len(raw))
                    if not chunk:
                        break
                    raw.extend(chunk)
                if len(raw) > 1024:
                    raise PdfPreparationError(422, "PDF inspector output exceeded bound")
                code = await process.wait()
                if code == 2:
                    raise PdfPreparationError(503, "PDF inspector unavailable")
                if code != 0:
                    raise PdfPreparationError(422, "PDF document failed bounded inspection")
                result = json.loads(raw)
                if (
                    not isinstance(result, dict)
                    or set(result) != {"pages", "bytes"}
                    or isinstance(result["pages"], bool)
                    or not isinstance(result["pages"], int)
                    or not 1 <= result["pages"] <= 4
                    or result["bytes"] != len(data)
                ):
                    raise PdfPreparationError(422, "Invalid PDF inspector metadata")
                return int(result["pages"])
        except TimeoutError as exc:
            raise PdfPreparationError(408, "PDF intake deadline exceeded") from exc
        except OSError as exc:
            raise PdfPreparationError(503, "PDF inspector unavailable") from exc
        except ValueError as exc:
            if isinstance(exc, PdfPreparationError):
                raise
            raise PdfPreparationError(422, "PDF document failed bounded inspection") from exc
        finally:
            await _bounded_pdf_reap(process, spawn)


pdf_preparer = PdfPreparer()
