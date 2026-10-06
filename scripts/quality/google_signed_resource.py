"""Validated synthetic signed quote/resource gate; no network or live credentials."""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import hmac
import importlib.util
import json
import time
from collections import Counter
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request
from google_live_runtime import QuietLogger
from google_resource_profile import StageProfile, drain_signed_capacity
from google_signed_process import configured
from openai import AsyncOpenAI, OpenAIError
from openai._models import FinalRequestOptions
from openai._response import AsyncAPIResponse
from openai._streaming import AsyncStream
from openai.types.responses import Response as SDKResponse
from openai.types.responses import ResponseStreamEvent

from foundry_router.api.adapters import google_schema
from foundry_router.api.google_history import project_context
from foundry_router.api.google_state import canonical_bytes
from foundry_router.api.google_work import SignedWorkLease
from foundry_router.api.routes.openai import build_router
from foundry_router.auth import verify_client_auth
from foundry_router.backends import AllowedBackendClient
from foundry_router.config.google_features import GoogleFeatureProfile
from foundry_router.credit import InMemoryCreditStore
from foundry_router.health import InMemoryHealthStore
from foundry_router.metrics import InMemoryMetricsStore
from foundry_router.ratelimit import InMemoryRateLimitStore

spec = importlib.util.spec_from_file_location(
    "rss_helpers", Path(__file__).with_name("google-output-png-benchmark.py")
)
assert spec is not None and spec.loader is not None
rss_helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rss_helpers)

SCANNER_SOURCE_SHA256 = hashlib.sha256(Path(google_schema.__file__).read_bytes()).hexdigest()

RSS_CAP = 128 * 1024 * 1024
LOOP_CAP_MS = 50
WIRE_CAP = 2097152
CARRIER_CAP = 524288
SEAL_HEADROOM = 393984
KNOWN_INPUT = 40
KNOWN_OUTPUT = 12
KNOWN_COST = 0.00076
COST_TOLERANCE = 1e-8
CONTEXT_QUOTE_CHARS = 65487
OUTPUT_PARTS = 2


def carrier_bytes(history):
    return sum(
        len(canonical_bytes(item["foundry_provider_state"]))
        for item in history
        if "foundry_provider_state" in item
    )


async def run(callers=8, attempts=100, *, preencoded=False, profile=False):  # noqa: PLR0912, PLR0915 -- complete resource ownership
    timing = StageProfile()
    settings = configured(False)
    settings.backends["g"].google_features = GoogleFeatureProfile(
        **{
            **settings.backends["g"].google_features.model_dump(),
            "signature_input_token_bound": 2000000,
        }
    )
    settings.backend_cycle_allowance_usd["g"] = 10000
    settings.backend_initial_estimated_remaining_usd["g"] = 10000
    settings.quota_group_rate_limits["project"] = {"rpm": 100000, "tpm": 100000000}
    parts = [
        {"text": "synthetic-answer", "thoughtSignature": base64.b64encode(b"x" * 16384).decode()}
    ] * 2
    native = {
        "candidates": [{"content": {"role": "model", "parts": parts}, "finishReason": "STOP"}],
        "usageMetadata": {
            "promptTokenCount": KNOWN_INPUT,
            "candidatesTokenCount": 10,
            "thoughtsTokenCount": 2,
            "totalTokenCount": 52,
        },
    }
    dispatches = 0
    expected_signed_parts = []
    failures = Counter()
    outcomes = Counter()
    sequence = 0
    upstream_wire_sizes = []
    actual_wire_sizes = []
    actual_completion_sizes = []
    actual_carrier_sizes = []
    owned_workers = set()

    async def owned_thread(function, *args):
        task = asyncio.create_task(asyncio.to_thread(function, *args))
        owned_workers.add(task)

        def finished(completed):
            owned_workers.discard(completed)
            if not completed.cancelled():
                completed.exception()

        task.add_done_callback(finished)
        return await asyncio.shield(task)

    async def provider(request):
        nonlocal dispatches
        if (
            request.method != "POST"
            or request.url
            != "https://synthetic.example.test/v1beta/models/configured:generateContent"
        ):
            raise ValueError("Unexpected synthetic destination")
        upstream_wire_sizes.append(len(request.content))
        parse = timing.wrap("mock_provider_json_decode", json.loads) if profile else json.loads
        upstream = (
            await owned_thread(parse, request.content) if preencoded else parse(request.content)
        )
        actual = [
            part
            for message in upstream["contents"]
            for part in message["parts"]
            if "thoughtSignature" in part
        ]
        if actual != expected_signed_parts:
            raise ValueError("Synthetic native replay mismatch")
        dispatches += 1
        await asyncio.sleep(0.005)
        return httpx.Response(200, json=native)

    backend = AllowedBackendClient(settings=settings)
    await backend._client.aclose()
    backend._client = httpx.AsyncClient(transport=httpx.MockTransport(provider))
    credit = InMemoryCreditStore()
    quota = InMemoryRateLimitStore()
    app = FastAPI()

    async def authenticate(request: Request):
        nonlocal sequence
        if request.headers.get("authorization") != "Bearer synthetic-caller":
            raise HTTPException(status_code=401, detail="Invalid synthetic caller")
        sequence += 1
        request.state.request_key = f"owned-{sequence}"
        request.state.correlation_id = request.state.request_key
        request.state.google_state_key_configuration = settings.google_state_keys
        request.state.google_caller_scope = hmac.new(
            b"s" * 32,
            b"caller\0synthetic-caller",
            hashlib.sha256,
        ).hexdigest()
        return "synthetic-caller"

    app.dependency_overrides[verify_client_auth] = authenticate
    app.include_router(
        build_router(
            load_settings_fn=lambda: settings,
            get_backend_client_fn=lambda: backend,
            sleep_fn=asyncio.sleep,
            health_store=InMemoryHealthStore(),
            credit_store=credit,
            metrics_store=InMemoryMetricsStore(),
            rate_limit_store=quota,
            logger=QuietLogger(),
        )
    )

    async def record_wire(request):
        actual_wire_sizes.append(len(request.content))

    sdk = AsyncOpenAI(
        api_key="synthetic-caller",
        base_url="http://synthetic.test/openai/v1",
        http_client=httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), event_hooks={"request": [record_wire]}
        ),
        max_retries=0,
    )
    body = {
        "model": "m",
        "input": [{"role": "user", "content": "synthetic-question"}],
        "instructions": '"' * CONTEXT_QUOTE_CHARS,
        "foundry_provider_state": {"version": 1},
        "max_output_tokens": 10,
    }
    baseline = rss_helpers.aggregate_rss()
    peak = baseline
    active = True
    delays = []
    latencies = []

    async def monitor():
        nonlocal peak
        while active:
            started = time.monotonic()
            await asyncio.sleep(0.005)
            delays.append(max(0, time.monotonic() - started - 0.005))
            peak = max(peak, rss_helpers.aggregate_rss())

    fixed_wires = {}

    async def create(body, stream=False):  # noqa: PLR0912 -- explicit two client surfaces
        if preencoded and fixed_wires:
            result = await sdk._client.post(
                "http://synthetic.test/openai/v1/responses",
                content=fixed_wires[stream],
                headers={
                    "authorization": "Bearer synthetic-caller",
                    "content-type": "application/json",
                },
            )
            if result.status_code != httpx.codes.OK:
                result.raise_for_status()
            if stream:
                response = AsyncStream(cast_to=ResponseStreamEvent, response=result, client=sdk)
            else:
                response = await AsyncAPIResponse(
                    raw=result,
                    cast_to=SDKResponse,
                    client=sdk,
                    stream=False,
                    stream_cls=None,
                    options=FinalRequestOptions.construct(method="POST", url="/responses"),
                ).parse()

        else:
            response = await sdk.responses.create(
                model="m",
                input=body["input"],
                instructions=body["instructions"],
                max_output_tokens=10,
                stream=stream,
                extra_body={"foundry_provider_state": {"version": 1}},
            )
        if stream:
            terminal = None
            completions = 0
            async with response:
                async for event in response:
                    if event.type == "response.completed":
                        completions += 1
                        terminal = event.response
                    if event.type in {"response.failed", "response.incomplete", "error"}:
                        raise ValueError("Synthetic stream failed")
            if completions != 1 or terminal is None:
                raise ValueError("Synthetic stream lacks completion")
            response = terminal
        if (
            response.status != "completed"
            or response.usage is None
            or response.usage.input_tokens != KNOWN_INPUT
            or response.usage.output_tokens != KNOWN_OUTPUT
            or len(response.output) != OUTPUT_PARTS
        ):
            raise ValueError("Invalid synthetic completion")
        public = response.model_dump(exclude_none=True)
        if any("foundry_provider_state" not in item for item in public["output"]):
            raise ValueError("Synthetic carrier missing")

        def check_completion():
            actual_bytes = len(
                canonical_bytes({**body, "input": [*body["input"], *public["output"]]})
            )
            actual_carriers = carrier_bytes([*body["input"], *public["output"]])
            if actual_bytes + SEAL_HEADROOM + 256 > WIRE_CAP or actual_carriers > CARRIER_CAP:
                raise ValueError("Actual completion exceeds replay headroom")
            actual_completion_sizes.append(actual_bytes)
            actual_carrier_sizes.append(actual_carriers)

        check = (
            timing.wrap("harness_completion_check", check_completion)
            if profile
            else check_completion
        )
        if preencoded:
            await owned_thread(check)
        else:
            check()
        return public

    watcher = asyncio.create_task(monitor())
    try:
        if profile:
            timing.start()
        # Three turns: six carrier occurrences. Leave room for the next signed turn.
        for _index in range(3):
            try:
                initial = await create(body)
            except OpenAIError:
                raise ValueError(f"Synthetic seed {_index} failed") from None
            body["input"].extend(initial["output"])
            body["input"].append({"role": "user", "content": "synthetic-next"})
            expected_signed_parts.extend(parts)
        seed_dispatches = dispatches
        # Two completed model Parts plus the following caller turn require three
        # free history positions; retain authenticated prefixes and add tail users.
        history_bound = settings.backends["g"].google_features.max_history_items
        while len(body["input"]) < history_bound - OUTPUT_PARTS - 1:
            body["input"].append({"role": "user", "content": "synthetic-tail"})
        probe = {**body, "input": [*body["input"][:-1], {"role": "user", "content": ""}]}
        base_size = len(canonical_bytes({**probe, "input": [*probe["input"], *initial["output"]]}))
        quote_chars = (WIRE_CAP - SEAL_HEADROOM - base_size - 512) // 2
        if quote_chars <= 0:
            raise ValueError("Synthetic quote fixture has no headroom")
        body["input"][-1]["content"] = '"' * quote_chars
        prospective_bytes = len(
            canonical_bytes({**body, "input": [*body["input"], *initial["output"]]})
        )
        if prospective_bytes + SEAL_HEADROOM > WIRE_CAP:
            raise ValueError("Synthetic fixture exceeds sealing headroom")
        dimensions = {
            "context_canonical_bytes": len(
                canonical_bytes(project_context(body, settings.backends["g"].google_features))
            ),
            "request_canonical_bytes": len(canonical_bytes(body)),
            "instruction_quote_characters": CONTEXT_QUOTE_CHARS,
            "input_quote_characters": quote_chars,
            "input_history_items": len(body["input"]),
            "input_carrier_bytes": carrier_bytes(body["input"]),
            "prospective_carrier_bytes": carrier_bytes([*body["input"], *initial["output"]]),
            "prospective_canonical_bytes": prospective_bytes,
            "reserved_next_turn_headroom_bytes": SEAL_HEADROOM,
            "signature_decoded_bytes_per_turn": 32768,
        }

        if preencoded:
            fixed_wires.update(
                {
                    stream: json.dumps({**body, "stream": stream}).encode()
                    for stream in (False, True)
                }
            )

        async def caller():
            for index in range(attempts):
                started = time.monotonic()
                stream = bool(index % 2)
                try:
                    public = await create(body, stream)
                    outcomes["stream_completed" if stream else "nonstream_completed"] += 1
                    del public
                except (OpenAIError, httpx.HTTPStatusError) as exc:
                    status = getattr(exc, "status_code", None)
                    if isinstance(exc, httpx.HTTPStatusError):
                        status = exc.response.status_code
                    failures[str(status) if status is not None else "sdk_error"] += 1
                except ValueError as exc:
                    safe_reasons = {
                        "Actual completion exceeds replay headroom",
                        "Invalid synthetic completion",
                        "Synthetic carrier missing",
                        "Synthetic decoded stream failed",
                        "Synthetic decoded stream lacks completion",
                    }
                    reason = str(exc) if str(exc) in safe_reasons else type(exc).__name__
                    failures[reason] += 1
                latencies.append(time.monotonic() - started)
                await asyncio.sleep(0.001)

        load_timed_out = False
        try:
            async with asyncio.timeout(60):
                await asyncio.gather(*(caller() for _ in range(callers)))
        except TimeoutError:
            load_timed_out = True
            failures["load_timeout"] += 1
        if asyncio.current_task().cancelling():
            raise asyncio.CancelledError
        workers_drained = True
        if owned_workers:
            try:
                async with asyncio.timeout(2):
                    await asyncio.shield(
                        asyncio.gather(*tuple(owned_workers), return_exceptions=True)
                    )
            except TimeoutError:
                workers_drained = False
        capacity_drained = await drain_signed_capacity()
        snapshots = await credit.live_snapshot(
            ["g"], min_credit_reserve_usd=0, min_credit_reserve_percent=0
        )
        snapshot = snapshots["g"]
        quota_state = (await quota.snapshot_quota_groups(["project"]))["project"]
        settled = (
            snapshot.active_reservations == 0
            and snapshot.reserved_inflight_usd == 0
            and not credit._reservations
            and not quota._reservations
            and abs(10000 - snapshot.estimated_remaining_usd - dispatches * KNOWN_COST)
            < COST_TOLERANCE
            and quota_state.rpm_used_60s == dispatches
            and quota_state.input_tpm_used_60s == dispatches * KNOWN_INPUT
        )
        if capacity_drained:
            leases = [SignedWorkLease(), SignedWorkLease()]
            for lease in leases:
                lease.close()
        return {
            "synthetic_only": True,
            "scanner_module_path": google_schema.__file__,
            "scanner_source_sha256": SCANNER_SOURCE_SHA256,
            "largest_upstream_request_wire_bytes": max(upstream_wire_sizes),
            "scope": (
                "preencoded HTTP with pinned SDK decoded responses; full process RSS"
                if preencoded
                else "full SDK request/response and router process RSS"
            ),
            "profile": timing.facts() if profile else None,
            "workload": "quote-heavy-feasible-completion",
            "callers": callers,
            "attempts_per_caller": attempts,
            "dimensions": {
                **dimensions,
                "largest_actual_sdk_request_wire_bytes": max(actual_wire_sizes),
                "largest_actual_completed_replay_canonical_bytes": max(actual_completion_sizes),
                "largest_actual_completed_carrier_bytes": max(actual_carrier_sizes),
            },
            "seed_dispatches": seed_dispatches,
            "load_dispatches": dispatches - seed_dispatches,
            "load_timed_out": load_timed_out,
            "signed_capacity_drained": capacity_drained,
            "harness_workers_drained": workers_drained,
            "outcomes": dict(outcomes),
            "failures": dict(failures),
            "settlement_and_quota_valid": settled,
            "active_credit_reservations": snapshot.active_reservations,
            "baseline_parent_children_rss": baseline,
            "peak_parent_children_rss": peak,
            "incremental_parent_children_rss": peak - baseline,
            "max_loop_delay_ms": max(delays, default=0) * 1000,
            "max_request_ms": max(latencies, default=0) * 1000,
            "passed": workers_drained
            and capacity_drained
            and settled
            and sum(outcomes.values()) == dispatches - seed_dispatches
            and outcomes["stream_completed"] > 0
            and outcomes["nonstream_completed"] > 0
            and set(failures) <= {"503"}
            and peak - baseline <= RSS_CAP
            and max(delays, default=0) * 1000 <= LOOP_CAP_MS,
        }
    finally:

        async def cleanup():
            nonlocal active
            active = False
            await watcher
            if owned_workers:
                await asyncio.gather(*tuple(owned_workers), return_exceptions=True)
            try:
                await sdk.close()
            finally:
                try:
                    await backend.aclose()
                finally:
                    app.dependency_overrides.clear()
                    timing.close()

        cleanup_task = asyncio.create_task(cleanup())
        while not cleanup_task.done():
            try:
                await asyncio.shield(cleanup_task)
            except asyncio.CancelledError:
                continue
        cleanup_task.result()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--preencoded", action="store_true")
    parser.add_argument("--profile", action="store_true")
    parser.add_argument("--callers", type=int, default=8)
    parser.add_argument("--attempts", type=int, default=100)
    args = parser.parse_args()
    result = asyncio.run(
        run(args.callers, args.attempts, preencoded=args.preencoded, profile=args.profile)
    )
    print(json.dumps(result, sort_keys=True))
    raise SystemExit(0 if result["passed"] else 1)
