"""Bounded Azure intake with default-off native route activation."""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import shutil
import stat
import sys
import tempfile
import time
import uuid
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, TypeVar

import httpx
from pydantic import BaseModel, ConfigDict, Field, model_validator
from structlog import get_logger

from foundry_router.api.adapters.google_schema import load_bounded_json
from foundry_router.api.azure_intake_context import (
    PreparedAzureResponseContext,
    PreparedAzureResponsePolicy,
)
from foundry_router.credit import RequestEstimate

logger = get_logger(__name__)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, AsyncIterator, Callable

_SOURCE_ROOT = str(Path(__file__).resolve().parents[2])
MIB = 1024 * 1024
SMALL_INPUT_BYTES = 2 * MIB
IO_CHUNK_BYTES = 64 * 1024
METADATA_BYTES = 128 * 1024
POLICY_BYTES = 32 * 1024
AZURE_PROVIDERS = frozenset({"azure_foundry", "azure_anthropic", "azure_mai"})
_STATE_KEY = "_foundry_azure_intake_delivery"
_T = TypeVar("_T")


class AzureIntakeError(ValueError):
    """A controlled preparation failure; it proves no dispatch for this preparation."""

    def __init__(self, status: int, code: str) -> None:
        super().__init__(code)
        self.status = status
        self.code = code
        self.confirmed_pre_dispatch = True


class _FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, allow_inf_nan=False)


class AzureIntakeLimits(_FrozenModel):
    max_input_bytes: int = Field(ge=1024, le=1024 * MIB)
    max_output_bytes: int = Field(ge=1024, le=1024 * MIB)
    child_address_space_bytes: int = Field(ge=64 * MIB)
    child_cpu_seconds: int = Field(ge=1, le=120)
    scratch_bytes: int = Field(ge=1024)

    @model_validator(mode="after")
    def scratch_fits_pair(self) -> AzureIntakeLimits:
        if self.scratch_bytes < self.max_input_bytes + self.max_output_bytes:
            raise ValueError("Scratch must hold the complete input/output pair")
        return self


class _Price(_FrozenModel):
    input_per_million: float = Field(ge=0)
    output_per_million: float = Field(ge=0)
    cached_input_per_million: float | None = Field(default=None, ge=0)
    image_input_tokens: int | None = Field(default=None, ge=258)
    pdf_document_tokens: int | None = Field(default=None, ge=258)
    audio_file_tokens: int | None = Field(default=None, ge=96)
    video_file_tokens: int | None = Field(default=None, ge=558)
    image_output_per_image: float | None = Field(default=None, ge=0)
    audio_output_per_second: float | None = Field(default=None, ge=0)


class _Backend(_FrozenModel):
    provider: str = Field(min_length=1, max_length=64)
    deployment: str = Field(min_length=1, max_length=512)
    operations: tuple[Literal["responses", "embeddings"], ...]


class _Model(_FrozenModel):
    backends: tuple[str, ...]
    streaming_enabled: bool
    price: _Price | None


class _PolicyDocument(_FrozenModel):
    limits: AzureIntakeLimits
    ordinary_bytes: int = Field(ge=1024, le=100_000_000)
    ordinary_timeout_seconds: float = Field(gt=0, le=120)
    timeout_seconds: float = Field(gt=0, le=120)
    child_wall_timeout_seconds: float = Field(default=30.0, gt=0, le=120)
    native_only: bool = False
    aliases: dict[str, str]
    models: dict[str, _Model]
    backends: dict[str, _Backend]

    @model_validator(mode="after")
    def validate_references(self) -> _PolicyDocument:
        if self.limits.max_input_bytes < self.ordinary_bytes:
            raise ValueError("Azure envelope cannot lower the ordinary byte bound")
        for name, model in self.models.items():
            if not name or not model.backends or len(set(model.backends)) != len(model.backends):
                raise ValueError("Invalid model policy")
            if any(backend not in self.backends for backend in model.backends):
                raise ValueError("Unknown policy backend")
        if any(
            alias in self.models or target not in self.models
            for alias, target in self.aliases.items()
        ):
            raise ValueError("Invalid policy alias")
        return self


def _json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")
    ).encode()


@dataclass(frozen=True)
class AzureIntakePolicy:
    """Immutable serialized allow-list; settings credentials and endpoints never enter it."""

    wire: bytes

    def __post_init__(self) -> None:
        if not isinstance(self.wire, bytes) or len(self.wire) > POLICY_BYTES:
            raise ValueError("Policy exceeds its bounded metadata allowance")
        load_bounded_json(self.wire.decode(), max_bytes=POLICY_BYTES)
        _PolicyDocument.model_validate_json(self.wire)

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.wire).hexdigest()

    @property
    def document(self) -> _PolicyDocument:
        # Return a new projection; mutating a returned nested map cannot change the binding.
        return _PolicyDocument.model_validate_json(self.wire)

    @classmethod
    def from_settings(cls, settings: Any, *, native_only: bool = False) -> AzureIntakePolicy:
        memory = settings.azure_intake_child_address_space_bytes
        if memory is None:
            raise ValueError("An explicitly calibrated child address-space budget is required")
        wire_bound = settings.azure_effective_max_request_body_bytes
        timeout = settings.azure_effective_intake_timeout_seconds
        prices = {
            name: {field: getattr(price, field) for field in _Price.model_fields}
            for name, price in settings.pricing.items()
        }
        value = {
            "limits": {
                "max_input_bytes": wire_bound,
                "max_output_bytes": wire_bound,
                "child_address_space_bytes": memory,
                "child_cpu_seconds": max(
                    1,
                    math.ceil(
                        max(
                            timeout,
                            getattr(settings, "azure_intake_child_wall_timeout_seconds", 30.0),
                        )
                    ),
                ),
                "scratch_bytes": getattr(settings, "azure_intake_scratch_bytes", 2304 * MIB),
            },
            "ordinary_bytes": settings.max_request_body_bytes,
            "ordinary_timeout_seconds": settings.intake_timeout_seconds,
            "timeout_seconds": timeout,
            "child_wall_timeout_seconds": getattr(
                settings, "azure_intake_child_wall_timeout_seconds", 30.0
            ),
            "native_only": native_only,
            "aliases": dict(settings.model_aliases),
            "models": {
                name: {
                    "backends": list(pool.backends),
                    "streaming_enabled": pool.streaming_enabled,
                    "price": prices.get(name),
                }
                for name, pool in settings.models.items()
            },
            "backends": {
                name: {
                    "provider": backend.provider,
                    "deployment": backend.deployment or name,
                    "operations": list(backend.supported_operations or ()),
                }
                for name, backend in settings.backends.items()
            },
        }
        return cls(_json_bytes(value))


class PreparedEstimate(_FrozenModel):
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0)

    def request_estimate(self) -> RequestEstimate:
        return RequestEstimate(self.input_tokens, self.output_tokens, self.estimated_cost_usd)


class PreparedAzureIntake(_FrozenModel):
    policy_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    input_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    input_bytes: int = Field(gt=0)
    requested_model: str = Field(min_length=1, max_length=512)
    model: str = Field(min_length=1, max_length=512)
    operation: Literal["responses", "embeddings"]
    stream: bool
    backends: tuple[str, ...]
    accepted_backends: tuple[str, ...]
    max_encoded_bytes: int = Field(gt=0)
    estimate: PreparedEstimate
    response_context: PreparedAzureResponseContext | None = None


class PreparedAzureAttempt(_FrozenModel):
    policy_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    input_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    backend_id: str
    provider: str
    deployment: str
    output_bytes: int = Field(gt=0)
    output_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    response_context_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class _Rejection(_FrozenModel):
    status: Literal[400, 404, 408, 413, 422, 503]
    code: Literal[
        "invalid_request",
        "model_not_found",
        "request_timeout",
        "router_request_resource_exceeded",
        "router_intake_busy",
        "router_intake_unavailable",
        "unsupported_input",
        "streaming_not_supported",
        "request_estimation_unavailable",
    ]


class _WorkerReply(_FrozenModel):
    prepared: PreparedAzureIntake | None = None
    attempt: PreparedAzureAttempt | None = None
    error: _Rejection | None = None
    ready: Literal[True] | None = None

    @model_validator(mode="after")
    def exactly_one_result(self) -> _WorkerReply:
        if (
            sum(item is not None for item in (self.prepared, self.attempt, self.error, self.ready))
            != 1
        ):
            raise ValueError("Invalid child result shape")
        return self


class _WorkerControl(_FrozenModel):
    stage: Literal["prepare", "encode", "probe"]
    policy: _PolicyDocument
    policy_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    input_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    input_bytes: int = Field(gt=0)
    output_limit_bytes: int = Field(ge=1024)
    operation: Literal["responses", "embeddings"]
    started_monotonic: float = Field(ge=0)
    deadline_monotonic: float = Field(gt=0)
    prepared: PreparedAzureIntake | None = None
    backend_id: str | None = None


class AzureIntakeResources:
    """Nonqueued process-local admission; capacity remains charged until cleanup is proven."""

    def __init__(self, root: Path, limits: AzureIntakeLimits, *, small_slots: int = 32) -> None:
        if type(small_slots) is not int or not 1 <= small_slots <= 32:
            raise ValueError("Invalid small intake capacity")
        info = root.lstat()
        if (
            not stat.S_ISDIR(info.st_mode)
            or stat.S_IMODE(info.st_mode) != 0o700
            or info.st_uid != os.getuid()
        ):
            raise ValueError("Scratch root must be an existing private owned directory")
        self.root = root
        self.limits = limits
        self.small_slots = small_slots
        self.active = 0
        self.scratch_reserved = 0
        self.large_owner: AzureIntakeLease | None = None
        self.child_owner: AzureIntakeLease | None = None
        self.uncertain: set[AzureIntakeLease] = set()
        self.leases: set[AzureIntakeLease] = set()
        self.accepting = True

    @property
    def ready(self) -> bool:
        return self.accepting and not self.uncertain

    @property
    def small_reservation(self) -> int:
        return min(SMALL_INPUT_BYTES, self.limits.max_input_bytes) + min(
            2 * SMALL_INPUT_BYTES, self.limits.max_output_bytes
        )

    def acquire(self) -> AzureIntakeLease:
        if (
            not self.ready
            or self.active >= self.small_slots
            or self.scratch_reserved + self.small_reservation > self.limits.scratch_bytes
        ):
            raise AzureIntakeError(503, "router_intake_busy")
        lease = AzureIntakeLease(self)
        self.active += 1
        self.leases.add(lease)
        self.scratch_reserved += lease.reserved
        return lease

    def upgrade(self, lease: AzureIntakeLease) -> None:
        if self.large_owner is lease:
            return
        required = self.limits.max_input_bytes + self.limits.max_output_bytes
        delta = required - lease.reserved
        if (
            not self.ready
            or self.large_owner is not None
            or self.scratch_reserved + delta > self.limits.scratch_bytes
        ):
            raise AzureIntakeError(503, "router_intake_busy")
        self.large_owner = lease
        self.scratch_reserved += delta
        lease.reserved = required


class AzureIntakeLease:
    def __init__(self, resources: AzureIntakeResources) -> None:
        self.resources = resources
        self.reserved = resources.small_reservation
        self.started = time.monotonic()
        self.input_bytes = 0
        self._digest = hashlib.sha256()
        self._directory: Path | None = None
        self._io: asyncio.Task[Any] | None = None
        self._spawn: asyncio.Task[asyncio.subprocess.Process] | None = None
        self._process: asyncio.subprocess.Process | None = None
        self._wait: asyncio.Task[int] | None = None
        self._reap: asyncio.Task[bool] | None = None
        self._cleanup: asyncio.Task[bool] | None = None
        self._reader: Any = None
        self._sealed = False
        self._failed_io = False
        self._closing = False
        self.closed = False
        self._delivery_transferred = False
        self.delivery_cleanup: Any = None
        self.prepared: PreparedAzureIntake | None = None
        self.attempt: PreparedAzureAttempt | None = None

    @property
    def input_path(self) -> Path:
        if self._directory is None:
            raise AzureIntakeError(503, "router_intake_unavailable")
        return self._directory / "input.json"

    @property
    def output_path(self) -> Path:
        return self.input_path.with_name("output.json")

    async def _run_io(self, operation: Callable[[], _T]) -> _T:
        if self._io is not None:
            raise AzureIntakeError(503, "router_intake_busy")
        task = asyncio.create_task(asyncio.to_thread(operation))
        self._io = task
        try:
            return await asyncio.shield(task)
        finally:
            if task.done():
                self._io = None

    def _create_spools(self) -> None:
        self._directory = Path(tempfile.mkdtemp(prefix="azure-intake-", dir=self.resources.root))
        for path in (self.input_path, self.output_path):
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
            os.close(descriptor)

    def _write(self, chunk: bytes) -> None:
        descriptor = os.open(self.input_path, os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW)
        with os.fdopen(descriptor, "wb", buffering=0) as handle:
            view = memoryview(chunk)
            for offset in range(0, len(view), IO_CHUNK_BYTES):
                piece = view[offset : offset + IO_CHUNK_BYTES]
                while piece:
                    count = handle.write(piece)
                    if count is None or count <= 0:
                        raise OSError("Incomplete private spool write")
                    piece = piece[count:]
            self._digest.update(chunk)
            self.input_bytes += len(chunk)

    async def write(self, chunk: bytes) -> None:
        if self._closing or self._sealed or self._failed_io or not isinstance(chunk, bytes):
            raise AzureIntakeError(503, "router_intake_unavailable")
        if len(chunk) > self.resources.limits.max_input_bytes - self.input_bytes:
            raise AzureIntakeError(413, "invalid_request")
        if self.input_bytes + len(chunk) > SMALL_INPUT_BYTES:
            self.resources.upgrade(self)
        try:
            if self._directory is None:
                await self._run_io(self._create_spools)
            await self._run_io(lambda: self._write(chunk))
        except OSError as exc:
            self._failed_io = True
            raise AzureIntakeError(503, "router_intake_unavailable") from exc

    async def _reap_child(self) -> bool:
        if self._spawn is None:
            return True
        if self._spawn.cancelled():
            self.resources.uncertain.add(self)
            return False
        if self._spawn.done() and self._spawn.exception() is not None:
            self._spawn = None
            if self.resources.child_owner is self:
                self.resources.child_owner = None
            return True
        try:
            async with asyncio.timeout(2):
                if self._process is None:
                    self._process = await asyncio.shield(self._spawn)
                if self._wait is None:
                    self._wait = asyncio.create_task(self._process.wait())
                if self._process.returncode is None:
                    with suppress(ProcessLookupError):
                        self._process.terminate()
                try:
                    async with asyncio.timeout(0.5):
                        await asyncio.shield(self._wait)
                except TimeoutError:
                    if self._process.returncode is None:
                        with suppress(ProcessLookupError):
                            self._process.kill()
                    await asyncio.shield(self._wait)
        except (TimeoutError, OSError):
            self.resources.uncertain.add(self)
            return False
        self._spawn = None
        self._process = None
        self._wait = None
        if self.resources.child_owner is self:
            self.resources.child_owner = None
        return True

    async def _finish_child(self) -> bool:
        if self._reap is None or self._reap.done():
            self._reap = asyncio.create_task(self._reap_child())
        return await asyncio.shield(self._reap)

    def _validate_prepared(
        self, value: PreparedAzureIntake, policy: AzureIntakePolicy, operation: str
    ) -> None:
        document = policy.document
        model = document.models.get(value.model)
        if (
            value.policy_digest != policy.digest
            or value.input_digest != self._digest.hexdigest()
            or value.input_bytes != self.input_bytes
            or value.operation != operation
            or document.aliases.get(value.requested_model, value.requested_model) != value.model
            or model is None
            or value.backends != model.backends
            or not value.accepted_backends
            or value.accepted_backends
            != tuple(name for name in model.backends if name in value.accepted_backends)
            or (value.stream and not model.streaming_enabled)
            or model.price is None
            or not 0 < value.max_encoded_bytes <= self.resources.limits.max_output_bytes
            or any(
                document.backends[name].provider
                not in ({"azure_foundry"} if document.native_only else AZURE_PROVIDERS)
                or operation not in document.backends[name].operations
                for name in value.backends
            )
        ):
            raise AzureIntakeError(503, "router_intake_unavailable")
        expected_policies = tuple(
            PreparedAzureResponsePolicy.model_validate(
                {
                    "backend_id": name,
                    "provider": document.backends[name].provider,
                    "kind": "one_png"
                    if document.backends[name].provider == "azure_mai"
                    else "text",
                }
            )
            for name in value.accepted_backends
            if document.backends[name].provider in {"azure_anthropic", "azure_mai"}
        )
        context = value.response_context
        if expected_policies:
            if (
                context is None
                or context.policy_digest != policy.digest
                or context.input_digest != value.input_digest
                or context.model != value.model
                or context.operation != operation
                or context.policies != expected_policies
            ):
                raise AzureIntakeError(503, "router_intake_unavailable")
        elif context is not None:
            raise AzureIntakeError(503, "router_intake_unavailable")
        price = model.price
        try:
            if all(document.backends[name].provider == "azure_mai" for name in value.backends):
                expected = price.image_output_per_image
                if value.estimate.input_tokens or value.estimate.output_tokens:
                    expected = None
            else:
                expected = (
                    value.estimate.input_tokens * price.input_per_million
                    + value.estimate.output_tokens * price.output_per_million
                ) / 1_000_000
        except OverflowError as exc:
            raise AzureIntakeError(503, "router_intake_unavailable") from exc
        if (
            expected is None
            or not math.isfinite(expected)
            or expected != value.estimate.estimated_cost_usd
        ):
            raise AzureIntakeError(503, "router_intake_unavailable")

    async def _child(self, control: _WorkerControl, deadline: float) -> _WorkerReply:
        if (
            self._closing
            or self._failed_io
            or not self.resources.ready
            or self.resources.child_owner is not None
        ):
            raise AzureIntakeError(503, "router_intake_busy")
        self.resources.child_owner = self
        raw = control.model_dump_json().encode()
        if len(raw) > METADATA_BYTES:
            self.resources.child_owner = None
            raise AzureIntakeError(503, "router_intake_unavailable")
        limits = self.resources.limits
        bootstrap = "import sys; sys.path.insert(0, sys.argv.pop(1)); from foundry_router.api.azure_intake_worker import main; raise SystemExit(main())"
        self._spawn = asyncio.create_task(
            asyncio.create_subprocess_exec(
                sys.executable,
                "-I",
                "-c",
                bootstrap,
                _SOURCE_ROOT,
                str(self.input_path),
                str(self.output_path),
                str(limits.child_address_space_bytes),
                str(limits.child_cpu_seconds),
                str(control.output_limit_bytes),
                str(deadline),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                limit=METADATA_BYTES + 1,
                env={"PATH": "", "PYTHONDONTWRITEBYTECODE": "1"},
                close_fds=True,
                start_new_session=True,
            )
        )
        try:
            async with asyncio.timeout_at(deadline):
                self._process = await asyncio.shield(self._spawn)
                self._wait = asyncio.create_task(self._process.wait())
                if self._process.stdin is None or self._process.stdout is None:
                    raise AzureIntakeError(503, "router_intake_unavailable")
                self._process.stdin.write(raw)
                await self._process.stdin.drain()
                self._process.stdin.close()
                await self._process.stdin.wait_closed()
                metadata = bytearray()
                while len(metadata) <= METADATA_BYTES:
                    chunk = await self._process.stdout.read(METADATA_BYTES + 1 - len(metadata))
                    if not chunk:
                        break
                    metadata.extend(chunk)
                code = await asyncio.shield(self._wait)
                if len(metadata) > METADATA_BYTES or code != 0:
                    raise AzureIntakeError(503, "router_intake_unavailable")
                load_bounded_json(metadata.decode(), max_bytes=METADATA_BYTES)
                return _WorkerReply.model_validate_json(metadata)
        except TimeoutError as exc:
            raise AzureIntakeError(408, "request_timeout") from exc
        except (OSError, ValueError) as exc:
            if isinstance(exc, AzureIntakeError):
                raise
            raise AzureIntakeError(503, "router_intake_unavailable") from exc
        finally:
            await self._finish_child()

    def _control(
        self,
        policy: AzureIntakePolicy,
        operation: Literal["responses", "embeddings"],
        deadline: float,
        *,
        backend_id: str | None = None,
    ) -> _WorkerControl:
        if (
            policy.document.limits != self.resources.limits
            or self._directory is None
            or not self.input_bytes
            or self._io is not None
            or self._failed_io
            or self._closing
        ):
            raise AzureIntakeError(503, "router_intake_unavailable")
        if backend_id is None:
            if deadline > self.started + policy.document.timeout_seconds:
                raise AzureIntakeError(408, "request_timeout")
        else:
            deadline = min(deadline, time.monotonic() + policy.document.child_wall_timeout_seconds)
        if time.monotonic() >= deadline:
            raise AzureIntakeError(408, "request_timeout")
        self._sealed = True
        limits = self.resources.limits
        return _WorkerControl(
            stage="prepare" if backend_id is None else "encode",
            policy=policy.document,
            policy_digest=policy.digest,
            input_digest=self._digest.hexdigest(),
            input_bytes=self.input_bytes,
            output_limit_bytes=(
                limits.max_output_bytes
                if self.resources.large_owner is self
                else min(limits.max_output_bytes, 2 * SMALL_INPUT_BYTES)
            ),
            operation=operation,
            started_monotonic=self.started,
            deadline_monotonic=deadline,
            prepared=self.prepared,
            backend_id=backend_id,
        )

    async def prepare(
        self,
        policy: AzureIntakePolicy,
        operation: Literal["responses", "embeddings"],
        *,
        deadline: float,
    ) -> PreparedAzureIntake:
        reply = await self._child(self._control(policy, operation, deadline), deadline)
        if reply.error is not None:
            raise AzureIntakeError(reply.error.status, reply.error.code)
        if reply.prepared is None:
            raise AzureIntakeError(503, "router_intake_unavailable")
        self._validate_prepared(reply.prepared, policy, operation)
        self.prepared = reply.prepared
        return reply.prepared

    def _verify_output(self, attempt: PreparedAzureAttempt) -> None:
        digest = hashlib.sha256()
        count = 0
        descriptor = os.open(self.output_path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(descriptor, "rb") as handle:
            while chunk := handle.read(IO_CHUNK_BYTES):
                count += len(chunk)
                if count > self.resources.limits.max_output_bytes:
                    raise ValueError("Output exceeds its bound")
                digest.update(chunk)
        if count != attempt.output_bytes or digest.hexdigest() != attempt.output_digest:
            raise ValueError("Output binding mismatch")

    async def encode(
        self, policy: AzureIntakePolicy, backend_id: str, *, deadline: float
    ) -> PreparedAzureAttempt:
        prepared = self.prepared
        if prepared is None or self._reader is not None or self._delivery_transferred:
            raise AzureIntakeError(503, "router_intake_unavailable")
        self._validate_prepared(prepared, policy, prepared.operation)
        if backend_id not in prepared.accepted_backends:
            raise AzureIntakeError(503, "router_intake_unavailable")
        # The child proved the encoded envelope using the mature serializer.
        # Promote only this request's actual possible output, preserving small capacity.
        if prepared.max_encoded_bytes > min(
            self.resources.limits.max_output_bytes, 2 * SMALL_INPUT_BYTES
        ):
            self.resources.upgrade(self)
        # A failed/cancelled replacement never authorizes reading the previous capability.
        self.attempt = None
        control = self._control(policy, prepared.operation, deadline, backend_id=backend_id)
        reply = await self._child(control, control.deadline_monotonic)
        if reply.error is not None:
            raise AzureIntakeError(reply.error.status, reply.error.code)
        attempt = reply.attempt
        backend = policy.document.backends[backend_id]
        if (
            attempt is None
            or attempt.policy_digest != policy.digest
            or attempt.input_digest != prepared.input_digest
            or attempt.backend_id != backend_id
            or attempt.provider != backend.provider
            or attempt.deployment != backend.deployment
            or attempt.output_bytes > self.resources.limits.max_output_bytes
            or attempt.response_context_digest
            != (prepared.response_context.digest if prepared.response_context is not None else None)
        ):
            raise AzureIntakeError(503, "router_intake_unavailable")
        try:
            await self._run_io(lambda: self._verify_output(attempt))
        except (OSError, ValueError) as exc:
            raise AzureIntakeError(503, "router_intake_unavailable") from exc
        self.attempt = attempt
        return attempt

    async def input_chunks(self) -> AsyncGenerator[bytes, None]:
        if self._closing or self._reader is not None:
            raise AzureIntakeError(503, "router_intake_unavailable")
        self._sealed = True

        def open_reader() -> None:
            self._reader = os.fdopen(os.open(self.input_path, os.O_RDONLY | os.O_NOFOLLOW), "rb")

        await self._run_io(open_reader)
        try:
            while chunk := await self._run_io(lambda: self._reader.read(IO_CHUNK_BYTES)):
                yield chunk
        finally:
            await self.drain_reader()

    async def drain_reader(self) -> None:
        if self._io is not None:
            task = self._io
            try:
                await asyncio.shield(task)
            finally:
                if task.done():
                    self._io = None
        if self._reader is not None:
            await self._run_io(self._close_reader)

    async def output_chunks(self, attempt: PreparedAzureAttempt) -> AsyncGenerator[bytes, None]:
        if (
            self._closing
            or not isinstance(attempt, PreparedAzureAttempt)
            or attempt != self.attempt
            or self._reader is not None
        ):
            raise AzureIntakeError(503, "router_intake_unavailable")

        def open_reader() -> None:
            descriptor = os.open(self.output_path, os.O_RDONLY | os.O_NOFOLLOW)
            self._reader = os.fdopen(descriptor, "rb")

        await self._run_io(open_reader)
        try:
            while chunk := await self._run_io(lambda: self._reader.read(IO_CHUNK_BYTES)):
                yield chunk
        finally:
            await self.drain_reader()

    def _close_reader(self) -> None:
        if self._reader is not None:
            self._reader.close()
            self._reader = None

    def _remove_spools(self) -> None:
        self._close_reader()
        if self._directory is not None:
            for name in ("input.json", "output.json"):
                (self._directory / name).unlink(missing_ok=True)
            self._directory.rmdir()
            self._directory = None

    async def _close(self) -> bool:
        if self.delivery_cleanup is not None:
            try:
                await self.delivery_cleanup()
            except (Exception, asyncio.CancelledError) as exc:
                self.resources.uncertain.add(self)
                logger.warning(
                    "azure_intake_delivery_cleanup_unconfirmed", error_type=type(exc).__name__
                )
                return False
            self.delivery_cleanup = None
        if self._io is not None:
            try:
                async with asyncio.timeout(2):
                    await asyncio.shield(self._io)
            except TimeoutError:
                self.resources.uncertain.add(self)
                return False
            except (OSError, ValueError):
                self._failed_io = True
            finally:
                if self._io.done():
                    self._io = None
        if not await self._finish_child():
            return False
        try:
            await self._run_io(self._remove_spools)
        except OSError:
            self.resources.uncertain.add(self)
            return False
        self.resources.active -= 1
        self.resources.scratch_reserved -= self.reserved
        if self.resources.large_owner is self:
            self.resources.large_owner = None
        self.resources.uncertain.discard(self)
        self.resources.leases.discard(self)
        self.closed = True
        return True

    async def close(self) -> bool:
        if self.closed:
            return True
        self._closing = True
        if self._cleanup is None or self._cleanup.done():
            self._cleanup = asyncio.create_task(self._close())
        cancelled = False
        while not self._cleanup.done():
            try:
                await asyncio.shield(self._cleanup)
            except asyncio.CancelledError:
                cancelled = True
        result = self._cleanup.result()
        if cancelled:
            raise asyncio.CancelledError()
        return result


class AzureIntakeDeliveryOwner:
    """Own an intake lease transferred by a completed route."""

    def __init__(self) -> None:
        self.lease: AzureIntakeLease | None = None
        self.deadline: float | None = None
        self._finalized = False

    def transfer(self, lease: AzureIntakeLease, deadline: float) -> None:
        if (
            self._finalized
            or self.lease is not None
            or lease.closed
            or lease._closing
            or lease._delivery_transferred
            or not math.isfinite(deadline)
        ):
            raise ValueError("Invalid intake delivery transfer")
        lease._delivery_transferred = True
        self.lease = lease
        self.deadline = deadline

    async def finalize(self) -> None:
        self._finalized = True
        if self.lease is not None:
            await self.lease.close()


class AzureIntakeDeliveryMiddleware:
    """Own intake spools through actual delivery while retaining output finalizers."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        owner = AzureIntakeDeliveryOwner()
        scope.setdefault("state", {})[_STATE_KEY] = owner

        async def bounded_send(message: Any) -> None:
            if owner.lease is None:
                await send(message)
            else:
                async with asyncio.timeout_at(owner.deadline):
                    await send(message)

        try:
            await self.app(scope, receive, bounded_send)
        finally:
            await owner.finalize()


class AzureIntakeRuntime:
    """One private lifetime; failed startup remains visible without hiding health/admin."""

    def __init__(self, settings: Any) -> None:
        self.enabled = bool(getattr(settings, "azure_intake_enabled", False))
        self.policy: AzureIntakePolicy | None = None
        self.resources: AzureIntakeResources | None = None
        self._root: Path | None = None
        self._available = False
        self._probe_verified = False
        self._closing = False
        self._closed = False
        self._recovery: asyncio.Task[None] | None = None

    async def start(self, settings: Any) -> None:
        if not self.enabled or self._closing or self._closed:
            return
        probe_lease: AzureIntakeLease | None = None
        try:
            if sys.platform != "linux":
                raise ValueError("Linux resource controls required")  # noqa: TRY301 -- safe unavailable startup
            policy = AzureIntakePolicy.from_settings(settings, native_only=False)
            root = await asyncio.to_thread(
                lambda: Path(tempfile.mkdtemp(prefix="azure-intake-runtime-"))
            )
            self._root = root
            if shutil.disk_usage(root).free < policy.document.limits.scratch_bytes:
                raise ValueError("Insufficient private scratch capacity")  # noqa: TRY301 -- safe unavailable startup
            self.policy = policy
            self.resources = AzureIntakeResources(root, policy.document.limits)
            probe_lease = self.resources.acquire()
            await probe_lease.write(b'{"probe":true}')
            deadline = probe_lease.started + min(5.0, policy.document.timeout_seconds)
            control = probe_lease._control(policy, "responses", deadline).model_copy(
                update={"stage": "probe"}
            )
            reply = await probe_lease._child(control, deadline)
            if reply.ready is not True:
                raise AzureIntakeError(503, "router_intake_unavailable")
            self._probe_verified = True
            self._available = True
        except (OSError, ValueError, TimeoutError):
            self._available = False
        finally:
            if probe_lease is not None and not await probe_lease.close():
                self._available = False

    @property
    def ready(self) -> bool:
        return (
            not self._closing
            and not self._closed
            and self._available
            and self.resources is not None
            and self.resources.ready
        )

    def matches(self, settings: Any) -> bool:
        try:
            return (
                self.ready
                and self.policy is not None
                and self.policy.digest
                == AzureIntakePolicy.from_settings(settings, native_only=False).digest
            )
        except ValueError:
            return False

    def recover(self) -> None:
        if (
            not self._closing
            and not self._closed
            and self.resources is not None
            and self.resources.uncertain
            and (self._recovery is None or self._recovery.done())
        ):
            self._recovery = asyncio.create_task(self._recover())

    async def _recover(self) -> None:
        if self.resources is not None:
            for lease in tuple(self.resources.uncertain):
                try:
                    await lease.close()
                except (OSError, ValueError):
                    self.resources.uncertain.add(lease)
            self._available = (
                not self._closing
                and not self._closed
                and self._probe_verified
                and self.resources.ready
            )

    async def close(self) -> None:
        self._closing = True
        self._available = False
        if self.resources is not None:
            self.resources.accepting = False
        if self._recovery is not None:
            await asyncio.shield(self._recovery)
        if self.resources is not None:
            for lease in tuple(self.resources.leases):
                await lease.close()
        if self._root is not None and (self.resources is None or not self.resources.leases):
            await asyncio.to_thread(self._root.rmdir)
            self._root = None
        self._closed = self.resources is None or not self.resources.leases
        self._available = False

    def status(self, settings: Any) -> dict[str, Any]:
        resources = self.resources
        return {
            "enabled": self.enabled,
            "ready": self.matches(settings) if self.enabled else True,
            "max_input_bytes": settings.azure_effective_max_request_body_bytes,
            "intake_timeout_seconds": settings.azure_effective_intake_timeout_seconds,
            "child_wall_timeout_seconds": settings.azure_intake_child_wall_timeout_seconds,
            "scratch_reservation_bytes": settings.azure_intake_scratch_bytes,
            "active_leases": resources.active if resources is not None else 0,
            "large_active": resources is not None and resources.large_owner is not None,
            "child_active": resources is not None and resources.child_owner is not None,
            "cleanup_uncertain": len(resources.uncertain) if resources is not None else 0,
        }


@dataclass
class AzureIntakeRequest:
    """Ordinary body or typed prepared metadata, plus one owned delivery lifetime."""

    lease: AzureIntakeLease
    policy: AzureIntakePolicy
    intake_deadline: float
    body: dict[str, Any] | None = None
    prepared: PreparedAzureIntake | None = None
    delivery_deadline: float | None = None
    backend: str | None = None
    possible_dispatch: bool = False
    _dispatching: bool = False
    _unknown_attempts: int = 0
    _completed_cost: float | None = None
    _completed_input_tokens: int | None = None
    quota: AzureIntakeQuotaStore | None = None

    def validate(self, settings: Any, model: str, operation: str) -> None:
        value = self.prepared
        if value is None:
            return
        if (
            self.policy.document.native_only
            or self.policy.digest
            != AzureIntakePolicy.from_settings(settings, native_only=False).digest
            or value.model != model
            or value.operation != operation
        ):
            raise AzureIntakeError(503, "router_intake_unavailable")
        self.lease._validate_prepared(value, self.policy, operation)

    @property
    def estimate(self) -> RequestEstimate:
        if self.prepared is None:
            raise AzureIntakeError(503, "router_intake_unavailable")
        return self.prepared.estimate.request_estimate()

    def begin_backend(self, backend: str) -> None:
        if self.prepared is None or backend not in self.prepared.accepted_backends:
            raise AzureIntakeError(503, "router_intake_unavailable")
        if self.backend != backend:
            self.backend = backend
            self.possible_dispatch = False
            self._dispatching = False
            self._unknown_attempts = 0
            self._completed_cost = None
            self._completed_input_tokens = None

    async def encode(self, backend: str, deadline: float) -> PreparedAzureAttempt:
        self.begin_backend(backend)
        await self.lease.drain_reader()
        if self.lease.attempt is not None and self.lease.attempt.backend_id == backend:
            return self.lease.attempt
        return await self.lease.encode(self.policy, backend, deadline=deadline)

    def mark_dispatch(self, backend: str) -> None:
        if (
            self.backend != backend
            or self.lease.attempt is None
            or self.lease.attempt.backend_id != backend
        ):
            raise AzureIntakeError(503, "router_intake_unavailable")
        self.possible_dispatch = True
        self._dispatching = True
        if self.quota is not None:
            self.quota.current_dispatched = True

    def uncertain(self) -> None:
        if self._dispatching:
            self._unknown_attempts += 1
            self._dispatching = False

    def completed(self) -> None:
        self._dispatching = False

    def succeeded(self, cost: float, input_tokens: int) -> None:
        self._dispatching = False
        self._completed_cost = cost
        self._completed_input_tokens = input_tokens

    def financially_finalized(self) -> None:
        self._dispatching = False
        self._unknown_attempts = 0
        self._completed_cost = None
        self._completed_input_tokens = None

    @property
    def has_liability(self) -> bool:
        return self._dispatching or self._unknown_attempts > 0 or self._completed_cost is not None

    @property
    def settlement_input_tokens(self) -> int:
        return (
            self._completed_input_tokens
            if self._completed_input_tokens is not None
            else self.estimate.input_tokens
        )

    @property
    def uncertain_cost(self) -> float:
        current = (
            self._completed_cost
            if self._completed_cost is not None
            else int(self._dispatching) * self.estimate.estimated_cost_usd
        )
        return self.prior_uncertain_cost + current

    @property
    def prior_uncertain_cost(self) -> float:
        return self._unknown_attempts * self.estimate.estimated_cost_usd

    def response_context(self, backend: str) -> PreparedAzureResponseContext:
        value = self.prepared
        attempt = self.lease.attempt
        if (
            value is None
            or value.response_context is None
            or attempt is None
            or attempt.backend_id != backend
            or attempt.policy_digest != value.policy_digest
            or attempt.input_digest != value.input_digest
            or attempt.response_context_digest != value.response_context.digest
        ):
            raise AzureIntakeError(503, "router_intake_unavailable")
        value.response_context.for_backend(backend, attempt.provider)
        return value.response_context

    def content(self, backend: str) -> AzureSpoolContent:
        attempt = self.lease.attempt
        if (
            attempt is None
            or attempt.backend_id != backend
            or attempt.provider not in AZURE_PROVIDERS
        ):
            raise AzureIntakeError(503, "router_intake_unavailable")
        return AzureSpoolContent(self.lease, attempt)


class AzureIntakeQuotaStore:
    """Bind quota settlement to each actual prepared HTTP attempt."""

    def __init__(self, store: Any, intake: AzureIntakeRequest, settings: Any) -> None:
        self.store = store
        self.intake = intake
        self.settings = settings
        self.current_dispatched = False
        self.current_id: str | None = None
        self.group: str | None = None
        intake.quota = self

    def __getattr__(self, name: str) -> Any:
        return getattr(self.store, name)

    async def try_reserve_estimate(self, request_id: str, quota_group: str, **kwargs: Any) -> bool:
        self.current_dispatched = False
        self.current_id = request_id
        self.group = quota_group
        return bool(await self.store.try_reserve_estimate(request_id, quota_group, **kwargs))

    def bind_backend(self, backend_id: str, attempt_id: str) -> None:
        group = self.settings.backends[backend_id].quota_group or backend_id
        self.current_dispatched = False
        if group in self.settings.quota_group_rate_limits:
            self.current_id = attempt_id
            self.group = group
        else:
            self.current_id = None
            self.group = None

    async def retry(self, deadline: float) -> bool:
        if self.current_id is None or self.group is None:
            return True
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise AzureIntakeError(408, "request_timeout")
        await self.store.finalize_request(self.current_id)
        attempt_id = str(uuid.uuid4())
        reserved = bool(
            await self.store.try_reserve_estimate(
                attempt_id,
                self.group,
                estimated_input_tokens=self.intake.estimate.input_tokens,
                reservation_max_age_seconds=min(
                    remaining, self.settings.reservation_max_age_seconds
                ),
            )
        )
        if reserved:
            self.current_dispatched = False
            self.current_id = attempt_id
        return reserved

    async def finalize_request(
        self, request_id: str, *, actual_input_tokens: int | None = None
    ) -> None:
        _ = request_id
        if self.current_id is None:
            return
        if self.current_dispatched:
            await self.store.finalize_request(
                self.current_id, actual_input_tokens=actual_input_tokens
            )
        else:
            await self.store.release_request(self.current_id)

    async def release_request(self, request_id: str) -> None:
        _ = request_id
        if self.current_id is not None:
            await self.store.release_request(self.current_id)


class AzureSpoolContent(httpx.AsyncByteStream):
    def __init__(self, lease: AzureIntakeLease, attempt: PreparedAzureAttempt) -> None:
        self.lease = lease
        self.attempt = attempt
        self.iterator: AsyncGenerator[bytes, None] | None = None

    async def __aiter__(self) -> AsyncIterator[bytes]:
        if self.iterator is not None:
            raise AzureIntakeError(503, "router_intake_unavailable")
        self.iterator = self.lease.output_chunks(self.attempt)
        async for chunk in self.iterator:
            yield chunk

    async def aclose(self) -> None:
        if self.iterator is not None:
            await self.iterator.aclose()
        await self.lease.drain_reader()


def intake_runtime(request: Any) -> AzureIntakeRuntime | None:
    return getattr(request.app.state, "azure_intake_runtime", None)


def intake_delivery_owner(state: Any) -> AzureIntakeDeliveryOwner | None:
    owner = getattr(state, _STATE_KEY, None)
    return owner if isinstance(owner, AzureIntakeDeliveryOwner) else None
