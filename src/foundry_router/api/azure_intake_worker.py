"""Isolated Azure preparation child; only bounded typed metadata crosses stdout."""

from __future__ import annotations

import hashlib
import json
import math
import os
import resource
import stat
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, NoReturn

if TYPE_CHECKING:
    from foundry_router.api.azure_intake import (
        PreparedAzureIntake,
        _WorkerControl,
        _WorkerReply,
    )

_IO_BYTES = 65536
_METADATA_BYTES = 128 * 1024


def _limits(arguments: list[str]) -> tuple[Path, Path, float]:
    if sys.platform != "linux":
        raise ValueError("Azure preparation resource controls require Linux")
    if len(arguments) != 6:
        raise ValueError("Invalid worker arguments")
    source, output = Path(arguments[0]), Path(arguments[1])
    memory, cpu, file_bytes = (int(value) for value in arguments[2:5])
    deadline = float(arguments[5])
    if (
        memory < 64 * 1024 * 1024
        or not 1 <= cpu <= 120
        or file_bytes < 1024
        or not math.isfinite(deadline)
    ):
        raise ValueError("Invalid worker resource bounds")
    resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
    resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
    resource.setrlimit(resource.RLIMIT_FSIZE, (file_bytes, file_bytes))
    resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    if source.parent != output.parent or source == output:
        raise ValueError("Invalid spool pair")
    return source, output, deadline


def _owned_file(path: Path) -> None:
    info = path.lstat()
    parent = path.parent.lstat()
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_nlink != 1
        or stat.S_IMODE(info.st_mode) != 0o600
        or info.st_uid != os.getuid()
        or not stat.S_ISDIR(parent.st_mode)
        or stat.S_IMODE(parent.st_mode) != 0o700
        or parent.st_uid != os.getuid()
    ):
        raise ValueError("Invalid private spool ownership")


def _deadline(deadline: float) -> None:
    from foundry_router.api.azure_intake import AzureIntakeError  # noqa: PLC0415 -- limits first

    if time.monotonic() >= deadline:
        raise AzureIntakeError(408, "request_timeout")


def _read_input(path: Path, control: _WorkerControl) -> bytearray:
    _owned_file(path)
    if (
        path.stat().st_size != control.input_bytes
        or control.input_bytes > control.policy.limits.max_input_bytes
    ):
        raise ValueError("Input size binding mismatch")
    result = bytearray()
    digest = hashlib.sha256()
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, "rb") as handle:
        while chunk := handle.read(_IO_BYTES):
            if len(chunk) > control.input_bytes - len(result):
                raise ValueError("Input exceeded bound")
            result.extend(chunk)
            digest.update(chunk)
            _deadline(control.deadline_monotonic)
    if len(result) != control.input_bytes or digest.hexdigest() != control.input_digest:
        raise ValueError("Input digest binding mismatch")
    return result


def _invalid(control: _WorkerControl, status: int, code: str) -> NoReturn:
    from foundry_router.api.azure_intake import AzureIntakeError  # noqa: PLC0415 -- limits first

    if control.input_bytes > control.policy.ordinary_bytes:
        raise AzureIntakeError(413, "invalid_request")
    raise AzureIntakeError(status, code)


def _adapter(provider: str, control: _WorkerControl) -> Any:
    from foundry_router.api.adapters import get_adapter  # noqa: PLC0415 -- limits first

    budget = (
        control.policy.limits.max_input_bytes
        if provider in {"azure_anthropic", "azure_mai"}
        else None
    )
    return get_adapter(provider, azure_request_text_budget=budget)


def _encoded_upper_bound(body: dict[str, Any], control: _WorkerControl, accepted: list[str]) -> int:
    """Count the mature wire dialect; native model replacement has an exact size delta."""
    from foundry_router.api.azure_intake import AzureIntakeError  # noqa: PLC0415

    native_size: int | None = None
    maximum = 0
    for name in accepted:
        backend = control.policy.backends[name]
        if backend.provider == "azure_foundry":
            if native_size is None:
                native_size = len(json.dumps(body, allow_nan=False).encode())
            size = native_size
            if control.operation == "responses":
                size += len(json.dumps(backend.deployment).encode()) - len(
                    json.dumps(body["model"]).encode()
                )
        else:
            upstream = _adapter(backend.provider, control).build_upstream_body(
                control.operation, body, deployment=backend.deployment, default_output_tokens=4096
            )
            size = len(json.dumps(upstream, allow_nan=False).encode())
        maximum = max(maximum, size)
        _deadline(control.deadline_monotonic)
    if maximum > control.policy.limits.max_output_bytes:
        raise AzureIntakeError(413, "router_request_resource_exceeded")
    return maximum


def _prepare(raw: bytearray, control: _WorkerControl) -> tuple[dict[str, Any], PreparedAzureIntake]:
    from foundry_router.api.adapters.google_schema import load_bounded_json  # noqa: PLC0415
    from foundry_router.api.azure_intake import (  # noqa: PLC0415 -- limits first
        AZURE_PROVIDERS,
        AzureIntakeError,
        PreparedAzureIntake,
        PreparedEstimate,
    )
    from foundry_router.credit import (  # noqa: PLC0415
        RequestEstimationError,
        estimate_request_cost_checked,
    )

    _deadline(control.deadline_monotonic)
    try:
        body = load_bounded_json(raw.decode(), max_bytes=control.policy.limits.max_input_bytes)
    except (ValueError, RecursionError):
        _invalid(control, 400, "invalid_request")
    if (
        not isinstance(body, dict)
        or not isinstance(body.get("model"), str)
        or not body["model"].strip()
    ):
        _invalid(control, 422, "invalid_request")
    requested = str(body["model"])
    canonical = control.policy.aliases.get(requested, requested)
    pool = control.policy.models.get(canonical)
    if pool is None:
        _invalid(control, 404, "model_not_found")
    backends = [control.policy.backends[name] for name in pool.backends]
    eligible = all(
        backend.provider in ({"azure_foundry"} if control.policy.native_only else AZURE_PROVIDERS)
        and control.operation in backend.operations
        for backend in backends
    )
    if not eligible:
        _invalid(control, 503, "router_intake_unavailable")
    if (
        control.operation == "responses"
        and "stream" in body
        and not isinstance(body["stream"], bool)
    ):
        _invalid(control, 422, "invalid_request")
    stream = body.get("stream", False) if control.operation == "responses" else False
    if stream and not pool.streaming_enabled:
        _invalid(control, 400, "streaming_not_supported")
    if control.operation == "embeddings":
        value = body.get("input")
        if not isinstance(value, (str, list)) or (
            isinstance(value, list)
            and (not value or any(not isinstance(item, str) or not item.strip() for item in value))
        ):
            _invalid(control, 422, "invalid_request")
    body = {**body, "model": canonical}
    accepted = []
    for name, backend in zip(pool.backends, backends, strict=True):
        rejection = _adapter(backend.provider, control).check_request(
            control.operation, body, deadline_monotonic=control.deadline_monotonic
        )
        if rejection is None:
            accepted.append(name)

    if not accepted:
        _invalid(control, 422, "unsupported_input")
    if pool.price is None:
        raise AzureIntakeError(503, "router_intake_unavailable")
    # This is a private, explicit request envelope; no Settings instance is mutated.
    settings = SimpleNamespace(
        max_request_body_bytes=control.policy.limits.max_input_bytes,
        models={
            canonical: SimpleNamespace(
                backends=dict.fromkeys(pool.backends, 1.0), continuation_policy="unsigned"
            )
        },
        backends={
            name: SimpleNamespace(
                provider=backend.provider, google_features=SimpleNamespace(features=[])
            )
            for name, backend in zip(pool.backends, backends, strict=True)
        },
    )
    try:
        estimate = estimate_request_cost_checked(
            model=canonical,
            operation=control.operation,
            body=body,
            pricing={canonical: pool.price},
            settings=settings,
        )
    except RequestEstimationError as exc:
        raise AzureIntakeError(422, "request_estimation_unavailable") from exc
    if estimate is None:
        raise AzureIntakeError(503, "router_intake_unavailable")
    _deadline(control.deadline_monotonic)
    from foundry_router.api.azure_intake_context import (  # noqa: PLC0415 -- limits first
        PreparedAzureResponseContext,
        PreparedAzureResponsePolicy,
    )

    policies = tuple(
        PreparedAzureResponsePolicy.model_validate(
            {
                "backend_id": name,
                "provider": control.policy.backends[name].provider,
                "kind": "one_png"
                if control.policy.backends[name].provider == "azure_mai"
                else "text",
            }
        )
        for name in accepted
        if control.policy.backends[name].provider in {"azure_anthropic", "azure_mai"}
    )
    context = (
        PreparedAzureResponseContext(
            policy_digest=control.policy_digest,
            input_digest=control.input_digest,
            model=canonical,
            operation="responses",
            metadata=tuple((body.get("metadata") or {}).items()),
            policies=policies,
        )
        if policies
        else None
    )
    return body, PreparedAzureIntake(
        policy_digest=control.policy_digest,
        input_digest=control.input_digest,
        input_bytes=control.input_bytes,
        requested_model=requested,
        model=canonical,
        operation=control.operation,
        stream=stream,
        backends=pool.backends,
        accepted_backends=tuple(accepted),
        max_encoded_bytes=_encoded_upper_bound(body, control, accepted),
        response_context=context,
        estimate=PreparedEstimate(
            input_tokens=estimate.input_tokens,
            output_tokens=estimate.output_tokens,
            estimated_cost_usd=estimate.estimated_cost_usd,
        ),
    )


def run(control: _WorkerControl, source: Path, output: Path) -> _WorkerReply:
    from foundry_router.api.azure_intake import (  # noqa: PLC0415 -- limits first
        AzureIntakeError,
        PreparedAzureAttempt,
        _json_bytes,
        _Rejection,
        _WorkerReply,
    )

    try:
        if (
            hashlib.sha256(_json_bytes(control.policy.model_dump())).hexdigest()
            != control.policy_digest
        ):
            raise ValueError("Policy binding mismatch")  # noqa: TRY301 -- bounded rejection
        raw = _read_input(source, control)
        if control.stage == "probe":
            from foundry_router.api.adapters.google_schema import (  # noqa: PLC0415 -- limits first
                load_bounded_json,
            )

            if load_bounded_json(raw.decode(), max_bytes=1024) != {"probe": True}:
                raise ValueError("Invalid self-test input")  # noqa: TRY301 -- bounded rejection
            if json.loads(json.dumps({"probe": "é"})) != {"probe": "é"}:
                raise ValueError("Invalid self-test serialization")  # noqa: TRY301 -- bounded rejection
            return _WorkerReply(ready=True)
        body, prepared = _prepare(raw, control)
        del raw
        if control.stage == "prepare":
            return _WorkerReply(prepared=prepared)
        if control.prepared != prepared or control.backend_id not in prepared.accepted_backends:
            raise ValueError("Selected attempt binding mismatch")  # noqa: TRY301 -- bounded rejection
        backend = control.policy.backends[control.backend_id]
        upstream = _adapter(backend.provider, control).build_upstream_body(
            control.operation, body, deployment=backend.deployment, default_output_tokens=4096
        )
        # HTTPX 0.27 uses stdlib JSON defaults (ASCII escapes and spaces).
        encoded = json.dumps(upstream, allow_nan=False).encode()
        del body, upstream
        if len(encoded) > min(control.output_limit_bytes, prepared.max_encoded_bytes):
            raise AzureIntakeError(413, "router_request_resource_exceeded")  # noqa: TRY301 -- bounded rejection
        _owned_file(output)
        descriptor = os.open(output, os.O_WRONLY | os.O_TRUNC | os.O_NOFOLLOW)
        with os.fdopen(descriptor, "wb", buffering=0) as handle:
            view = memoryview(encoded)
            for offset in range(0, len(view), _IO_BYTES):
                piece = view[offset : offset + _IO_BYTES]
                while piece:
                    count = handle.write(piece)
                    if count is None or count <= 0:
                        raise OSError("Incomplete encoded spool write")  # noqa: TRY301 -- bounded rejection
                    piece = piece[count:]
                _deadline(control.deadline_monotonic)
        return _WorkerReply(
            attempt=PreparedAzureAttempt(
                policy_digest=control.policy_digest,
                input_digest=prepared.input_digest,
                backend_id=control.backend_id,
                provider=backend.provider,
                deployment=backend.deployment,
                output_bytes=len(encoded),
                output_digest=hashlib.sha256(encoded).hexdigest(),
                response_context_digest=prepared.response_context.digest
                if prepared.response_context
                else None,
            )
        )
    except AzureIntakeError as exc:
        return _WorkerReply(
            error=_Rejection.model_validate({"status": exc.status, "code": exc.code})
        )
    except (MemoryError, OverflowError):
        return _WorkerReply(error=_Rejection(status=413, code="router_request_resource_exceeded"))
    except (ValueError, OSError, RecursionError, TypeError):
        return _WorkerReply(error=_Rejection(status=503, code="router_intake_unavailable"))


def main() -> int:
    try:
        source, output, deadline = _limits(sys.argv[1:])
        # Heavy imports happen only after the resource controls are in force.
        from foundry_router.api.adapters.google_schema import load_bounded_json  # noqa: PLC0415
        from foundry_router.api.azure_intake import _WorkerControl  # noqa: PLC0415

        raw = sys.stdin.buffer.read(_METADATA_BYTES + 1)
        if len(raw) > _METADATA_BYTES:
            return 2
        load_bounded_json(raw.decode(), max_bytes=_METADATA_BYTES)
        control = _WorkerControl.model_validate_json(raw)
        if (
            control.deadline_monotonic != deadline
            or control.policy.limits.child_address_space_bytes != int(sys.argv[3])
            or control.policy.limits.child_cpu_seconds != int(sys.argv[4])
            or control.output_limit_bytes != int(sys.argv[5])
            or control.output_limit_bytes > control.policy.limits.max_output_bytes
        ):
            return 2
        reply = run(control, source, output).model_dump_json().encode()
        if len(reply) > _METADATA_BYTES:
            return 2
        sys.stdout.buffer.write(reply)
        sys.stdout.buffer.flush()
    except (ValueError, OSError, MemoryError, ImportError):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
