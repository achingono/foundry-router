"""Bounded native/Responses diagnostics with transient retries for Gemini 3.8."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import math
import time
from http import HTTPStatus
from pathlib import Path

import httpx
from google_compatible_runtime import run_compatible_case
from google_envelope_diagnostic import observe_schema, validate_schema
from google_live_budget import locked, write_atomic
from google_live_execute import fetch_project_credentials
from google_live_runtime import GuardedTransport

from foundry_router.api.adapters.google_schema import load_bounded_json
from foundry_router.forwarding import parse_retry_after

DIRECTORY = Path(__file__).resolve().parents[2] / "docs/plans/google-38-responses-diagnostics"
HISTORICAL = DIRECTORY.parent / "google-ai-routing-order/ledger-native-text-2026-10-08.json"
MODEL = "gemini-3.8-flash"
PROMPT = "Reply with the word ready."
RESERVED = 1088
MAX_OUTPUT = 1024
MAX_INPUT = 64
MAX_BODY = 4 * 1024 * 1024
MAX_CALLS = 15
MAX_PHYSICAL = 45
MAX_ATTEMPTS = 3
MAX_RETRY_WAIT = 30
MAX_SECONDS = 25
MAX_LOGICAL_SECONDS = 100
MAX_RETRY_HEADER = 31
MIN_HTTP = 100
MAX_HTTP = 599
ERROR_STATUSES = {
    "INVALID_ARGUMENT",
    "UNAVAILABLE",
    "RESOURCE_EXHAUSTED",
    "PERMISSION_DENIED",
    "NOT_FOUND",
    "UNAUTHENTICATED",
    "INTERNAL",
}


VERIFIED_CASE = "g38-verified-nonstream-project-1"

OBSERVATION_KEYS = {
    "provider_http_status",
    "provider_error_status",
    "failure_phase",
    "response_schema",
    "dimension_overrun",
    "retry_after_seconds",
}
NATIVE_KEYS = {
    "status",
    "surface",
    "model",
    "http_status",
    "actual_tokens",
    "input_tokens",
    "output_tokens",
    "budget_overrun",
    "public_completed",
    "elapsed_seconds",
}
COMPAT_KEYS = {
    "case_id",
    "project",
    "model",
    "surface",
    "stream",
    "thinking_policy",
    "status",
    "http_status",
    "provider_http_status",
    "dispatched",
    "actual_tokens",
    "input_tokens",
    "output_tokens",
    "thought_tokens",
    "budget_overrun",
    "public_completed",
    "public_text_present",
    "usage_matches",
    "synthetic_debit_usd",
    "settlement_matches",
    "reservations_cleared",
    "error_category",
    "elapsed_seconds",
}


def validate_observation(observation):
    if not isinstance(observation, dict) or set(observation) != OBSERVATION_KEYS:
        raise ValueError("Invalid observation fields")
    status = observation["provider_http_status"]
    if status is not None and (type(status) is not int or not MIN_HTTP <= status <= MAX_HTTP):
        raise ValueError("Invalid provider status")
    if observation["provider_error_status"] not in {*ERROR_STATUSES, "other", None}:
        raise ValueError("Invalid provider error enum")
    if observation["failure_phase"] not in {
        None,
        "response_headers",
        "response_body",
        "transport_or_protocol",
        "deadline_response_headers",
        "deadline_response_body",
        "unknown_or_deadline",
    }:
        raise ValueError("Invalid failure phase")
    if type(observation["dimension_overrun"]) is not bool:
        raise ValueError("Invalid dimension flag")
    delay = observation["retry_after_seconds"]
    if delay is not None and (
        type(delay) not in {int, float}
        or not math.isfinite(delay)
        or not 0 <= delay <= MAX_RETRY_HEADER
    ):
        raise ValueError("Invalid retry wait")
    if observation["response_schema"] is not None:
        validate_schema(observation["response_schema"])


def validate_result(result, observation):
    validate_observation(observation)
    if not isinstance(result, dict) or set(result) not in (NATIVE_KEYS, COMPAT_KEYS):
        raise ValueError("Invalid result fields")
    if (
        result["model"] != MODEL
        or result["status"] not in {"passed", "failed"}
        or result["surface"] not in {"native", "openai_compat"}
    ):
        raise ValueError("Invalid result enum")
    for name, value in result.items():
        if (
            name
            in {
                "budget_overrun",
                "public_completed",
                "stream",
                "dispatched",
                "public_text_present",
                "usage_matches",
                "settlement_matches",
                "reservations_cleared",
            }
            and type(value) is not bool
        ):
            raise ValueError("Invalid boolean")
        if (
            name
            in {
                "actual_tokens",
                "input_tokens",
                "output_tokens",
                "thought_tokens",
                "http_status",
                "provider_http_status",
            }
            and value is not None
            and (type(value) is not int or value < 0)
        ):
            raise ValueError("Invalid numeric count")
        if name in {"elapsed_seconds", "synthetic_debit_usd"}:  # noqa: SIM102 -- result field validation
            if (
                type(value) not in {int, float}
                or not math.isfinite(value)
                or not 0 <= value <= MAX_LOGICAL_SECONDS
            ):
                raise ValueError("Invalid bounded number")
    if "case_id" in result:
        if result["case_id"] not in {VERIFIED_CASE} | {
            f"g38-{surface}-project-{i}" for surface in ("nonstream", "stream") for i in range(1, 6)
        } or result["project"] not in {f"project-{i}" for i in range(1, 6)}:
            raise ValueError("Invalid case identity")
        if result["thinking_policy"] != "provider_default" or result["error_category"] not in {
            None,
            "provider_or_protocol_failure",
        }:
            raise ValueError("Invalid result policy")


def error_status(wire):
    try:
        data = load_bounded_json(wire.decode(), max_bytes=MAX_BODY)
    except (ValueError, UnicodeError):
        return "other"
    error = data.get("error") if isinstance(data, dict) else None
    status = error.get("status") if isinstance(error, dict) else None
    return status if isinstance(status, str) and status in ERROR_STATUSES else "other"


class DiagnosticLedger:
    """Whole-run lock is owned by execute; every attempt is persisted before dispatch."""

    def __init__(self, path, historical):
        self.path = path
        if path.exists():
            raise ValueError("Diagnostic stage already started; replay refused")
        self.data = {
            "stage": "google-38-diagnostics-2026-10-09",
            "historical_sha256": hashlib.sha256(historical).hexdigest(),
            "maximum_calls": MAX_CALLS,
            "maximum_provider_attempts": MAX_PHYSICAL,
            "maximum_reserved_tokens": MAX_PHYSICAL * RESERVED,
            "attempts": {},
            "halted": False,
        }
        write_atomic(path, self.data)

    def reserve(self, project, case, tokens):
        attempts = self.data["attempts"]
        allowed = {
            f"g38-{surface}-project-{i}"
            for i in range(1, 6)
            for surface in ("native", "nonstream", "stream")
        }
        if (
            case not in allowed | {VERIFIED_CASE}
            or not case.endswith(project)
            or project not in {f"project-{i}" for i in range(1, 6)}
            or tokens != RESERVED
            or case in attempts
            or self.data["halted"]
            or len(attempts) >= MAX_CALLS
            or any(item["result"] is None for item in attempts.values())
        ):
            raise ValueError("Diagnostic budget unavailable")
        attempts[case] = {
            "project": project,
            "reserved_tokens": tokens,
            "actual_tokens": None,
            "result": None,
            "physical_attempts": [],
        }
        write_atomic(self.path, self.data)

    def start_physical(self, case):
        item = self.data["attempts"][case]
        total = sum(len(x["physical_attempts"]) for x in self.data["attempts"].values())
        if (
            self.data["halted"]
            or len(item["physical_attempts"]) >= MAX_ATTEMPTS
            or total >= MAX_PHYSICAL
        ):
            raise ValueError("Physical budget unavailable")
        item["physical_attempts"].append(
            {
                "reserved_tokens": RESERVED,
                "actual_tokens": None,
                "observation": None,
                "retry_wait_seconds": 0,
            }
        )
        write_atomic(self.path, self.data)

    def finish_physical(self, case, observation):
        validate_observation(observation)
        self.data["attempts"][case]["physical_attempts"][-1]["observation"] = dict(observation)
        write_atomic(self.path, self.data)

    def note_wait(self, case, delay):
        self.data["attempts"][case]["physical_attempts"][-1]["retry_wait_seconds"] = delay
        write_atomic(self.path, self.data)

    def record_usage(self, project, case, tokens):
        if type(tokens) is not int or tokens < 0:
            raise ValueError("Invalid usage")
        item = self.data["attempts"][case]
        if item["project"] != project:
            raise ValueError("Usage owner mismatch")
        item["actual_tokens"] = max(item["actual_tokens"] or 0, tokens)
        attempts = item["physical_attempts"]
        if attempts:
            attempts[-1]["actual_tokens"] = max(attempts[-1]["actual_tokens"] or 0, tokens)
        self.data["halted"] |= tokens > RESERVED
        write_atomic(self.path, self.data)

    def finish(self, case, result, observation):
        validate_result(result, observation)
        item = self.data["attempts"][case]
        if result.get("actual_tokens") is not None:
            item["actual_tokens"] = max(item["actual_tokens"] or 0, result["actual_tokens"])
        if result["status"] == "passed" and result.get("actual_tokens") != item["actual_tokens"]:
            result["status"] = "failed"
        result["actual_tokens"] = item["actual_tokens"]
        result["budget_overrun"] = (
            result.get("budget_overrun", False) or observation["dimension_overrun"]
        )
        if result["budget_overrun"]:
            result["status"] = "failed"
        item["result"] = result
        item["observation"] = observation
        status = observation["provider_http_status"]
        known_unavailable = (
            status == HTTPStatus.SERVICE_UNAVAILABLE
            and observation["provider_error_status"] == "UNAVAILABLE"
        )
        transient_observed = status in {500, 502, 503, 504} or observation["failure_phase"] in {
            "response_headers",
            "response_body",
            "deadline_response_headers",
            "deadline_response_body",
        }
        self.data["halted"] |= (
            (observation["failure_phase"] is not None and not transient_observed)
            or result.get("budget_overrun", False)
            or status in {400, 401, 403, 404, 429}
            or (result["status"] != "passed" and not known_unavailable and not transient_observed)
        )
        write_atomic(self.path, self.data)


class ObservingTransport(httpx.AsyncBaseTransport):
    """Bounded in-memory provider body; persist only fixed shape/numeric observations."""

    def __init__(self, transport, ledger, project, case, *, native=False):
        self.transport = transport
        self.ledger = ledger
        self.project = project
        self.case = case
        self.native = native
        self.observation = {
            "provider_http_status": None,
            "provider_error_status": None,
            "failure_phase": None,
            "response_schema": None,
            "dimension_overrun": False,
            "retry_after_seconds": None,
        }
        self.native_usage = None
        self.native_completed = False
        self.stream_bytes_seen = False
        self.sleep = asyncio.sleep
        self.max_attempts = MAX_ATTEMPTS

    async def handle_async_request(self, request):
        for attempt in range(1, self.max_attempts + 1):
            self.ledger.start_physical(self.case)
            self.observation = {
                "provider_http_status": None,
                "provider_error_status": None,
                "failure_phase": None,
                "response_schema": None,
                "dimension_overrun": False,
                "retry_after_seconds": None,
            }
            response = None
            caught = None
            self.stream_bytes_seen = False
            self.native_usage = None
            self.native_completed = False
            try:
                async with asyncio.timeout(MAX_SECONDS):
                    response = await self._once(request)
            except (httpx.HTTPError, TimeoutError) as exc:
                caught = exc
                if response is not None:
                    await response.aclose()
                if self.observation["failure_phase"] is None:
                    self.observation["failure_phase"] = "unknown_or_deadline"
            self.ledger.finish_physical(self.case, self.observation)
            status = self.observation["provider_http_status"]
            retryable = status in {429, 500, 502, 503, 504} or caught is not None
            # 429 exhaustion dimension is not retained safely: withhold all quota retries.
            retryable = (
                retryable
                and status not in {400, 401, 403, 404, 429}
                and not self.observation["dimension_overrun"]
                and not self.stream_bytes_seen
            )
            if not retryable or attempt == self.max_attempts or self.ledger.data["halted"]:
                if caught is not None:
                    raise caught
                return response
            delay = max(2**attempt, self.observation["retry_after_seconds"] or 0)
            if delay > MAX_RETRY_WAIT:
                if caught is not None:
                    raise caught
                return response
            self.ledger.note_wait(self.case, delay)
            if response is not None:
                await response.aclose()
            await self.sleep(delay)
        raise RuntimeError("Attempt bound exceeded")

    async def _once(self, request):  # noqa: PLR0912 -- bounded observation and cleanup
        phase = "response_headers"
        response = None
        try:
            response = await self.transport.handle_async_request(request)
            self.observation["provider_http_status"] = response.status_code
            retry_after = response.headers.get("retry-after")
            if retry_after:
                self.observation["retry_after_seconds"] = parse_retry_after(
                    retry_after, MAX_RETRY_HEADER
                )
            phase = "response_body"
            body = bytearray()
            async for chunk in response.aiter_bytes():
                if len(body) + len(chunk) > MAX_BODY:
                    raise ValueError("Response bound exceeded")  # noqa: TRY301 -- bounded transport intake
                body.extend(chunk)
                if chunk and json.loads(request.content).get("stream"):
                    self.stream_bytes_seen = True
            wire = bytes(body)
            if response.status_code != HTTPStatus.OK:
                self.observation["provider_error_status"] = error_status(wire)
            elif self.native:
                self._native(wire)
            else:
                stream = bool(json.loads(request.content).get("stream"))
                self._compatible_usage(wire, stream)
                if not stream:
                    self.observation["response_schema"] = observe_schema(wire)
            return httpx.Response(response.status_code, headers=response.headers, content=wire)
        except httpx.TimeoutException:
            self.observation["failure_phase"] = phase
            raise
        except asyncio.CancelledError:
            self.observation["failure_phase"] = "deadline_" + phase
            raise
        except (httpx.HTTPError, ValueError):
            self.observation["failure_phase"] = "transport_or_protocol"
            raise
        finally:
            if response is not None:
                await response.aclose()

    def _dimensions(self, inputs, outputs):
        overrun = (type(inputs) is int and inputs > MAX_INPUT) or (
            type(outputs) is int and outputs > MAX_OUTPUT
        )
        if overrun:
            self.observation["dimension_overrun"] = True
            self.ledger.data["halted"] = True
            write_atomic(self.ledger.path, self.ledger.data)

    def _compatible_usage(self, wire, stream):
        payloads = (
            [
                line.strip()[5:].strip()
                for line in wire.splitlines()
                if line.strip().startswith(b"data:")
                and line.strip()[5:].strip() not in {b"", b"[DONE]"}
            ]
            if stream
            else [wire]
        )
        for payload in payloads:
            try:
                event = load_bounded_json(payload.decode(), max_bytes=MAX_BODY)
            except (ValueError, UnicodeError):
                continue
            usage = event.get("usage") if isinstance(event, dict) else None
            if not isinstance(usage, dict):
                continue
            counts = [usage.get(k) for k in ("prompt_tokens", "completion_tokens", "total_tokens")]
            details = usage.get("completion_tokens_details")
            reasoning = details.get("reasoning_tokens") if isinstance(details, dict) else None
            self._dimensions(
                counts[0],
                max(counts[1] or 0, reasoning or 0)
                if all(v is None or type(v) is int for v in (counts[1], reasoning))
                else counts[1],
            )
            valid = [v for v in [*counts, reasoning] if type(v) is int and v >= 0]
            lower = sum(v for v in counts[:2] if type(v) is int and v >= 0)
            if type(reasoning) is int and reasoning >= 0 and type(counts[0]) is int:
                lower = max(lower, counts[0] + reasoning)
            if valid:
                self.ledger.record_usage(self.project, self.case, max(*valid, lower))

    def _native(self, wire):
        data = load_bounded_json(wire.decode(), max_bytes=MAX_BODY)
        if not isinstance(data, dict):
            raise ValueError("Invalid native response")  # noqa: TRY004 -- sanitized protocol failure
        usage = data.get("usageMetadata", {})
        if isinstance(usage, dict):
            counts = [
                usage.get(k)
                for k in (
                    "promptTokenCount",
                    "candidatesTokenCount",
                    "thoughtsTokenCount",
                    "totalTokenCount",
                )
            ]
            valid = [v for v in counts if type(v) is int and v >= 0]
            lower = sum(v for v in counts[:3] if type(v) is int and v >= 0)
            if valid:
                self.ledger.record_usage(self.project, self.case, max(*valid, lower))
            inputs, outputs, thoughts, total = counts
            self._dimensions(
                inputs,
                (outputs or 0) + (thoughts or 0)
                if all(v is None or type(v) is int for v in (outputs, thoughts))
                else outputs,
            )
            thoughts = 0 if thoughts is None else thoughts
            if all(type(v) is int and v >= 0 for v in (inputs, outputs, thoughts, total)):
                self.native_usage = (inputs, outputs + thoughts, total)
        candidates = data.get("candidates")
        if (
            isinstance(candidates, list)
            and len(candidates) == 1
            and isinstance(candidates[0], dict)
        ):
            candidate = candidates[0]
            content = candidate.get("content", {})
            parts = content.get("parts", []) if isinstance(content, dict) else []
            self.native_completed = (
                candidate.get("finishReason") == "STOP"
                and isinstance(parts, list)
                and any(
                    isinstance(p, dict)
                    and isinstance(p.get("text"), str)
                    and bool(p["text"].strip())
                    for p in parts
                )
            )

    async def aclose(self):
        await self.transport.aclose()


async def native_case(key, ledger, project, case):
    observer = ObservingTransport(
        httpx.AsyncHTTPTransport(retries=0, trust_env=False), ledger, project, case, native=True
    )
    guard = GuardedTransport(
        observer,
        ledger=ledger,
        project=project,
        case_id=case,
        model=MODEL,
        expected_thinking={"thinkingLevel": "low"},
        output_tokens=MAX_OUTPUT,
        reserved_tokens=RESERVED,
        expected_prompt=PROMPT,
    )
    status = None
    try:
        async with (
            asyncio.timeout(MAX_LOGICAL_SECONDS),
            httpx.AsyncClient(transport=guard, timeout=20, trust_env=False) as client,
        ):
            response = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent",
                headers={"x-goog-api-key": key, "Accept-Encoding": "identity"},
                json={
                    "contents": [{"role": "user", "parts": [{"text": PROMPT}]}],
                    "generationConfig": {
                        "maxOutputTokens": MAX_OUTPUT,
                        "candidateCount": 1,
                        "responseModalities": ["TEXT"],
                        "thinkingConfig": {"thinkingLevel": "low"},
                    },
                },
            )
            status = response.status_code
    except (httpx.HTTPError, ValueError, TimeoutError):
        if (
            observer.observation["failure_phase"] is None
            and observer.observation["provider_http_status"] is None
        ):
            observer.observation["failure_phase"] = "unknown_or_deadline"
    usage = observer.native_usage
    passed = (
        status == HTTPStatus.OK
        and observer.native_completed
        and usage is not None
        and (usage[0] <= MAX_INPUT and usage[1] <= MAX_OUTPUT and usage[2] == usage[0] + usage[1])
        and not guard.overrun
        and not observer.observation["dimension_overrun"]
        and usage[2] == ledger.data["attempts"][case]["actual_tokens"]
    )
    result = {
        "status": "passed" if passed else "failed",
        "surface": "native",
        "model": MODEL,
        "http_status": status,
        "actual_tokens": ledger.data["attempts"][case]["actual_tokens"],
        "input_tokens": usage[0] if usage else None,
        "output_tokens": usage[1] if usage else None,
        "budget_overrun": guard.overrun or observer.observation["dimension_overrun"],
        "public_completed": observer.native_completed,
    }
    return result, observer.observation


async def execute(secret_ref):
    path = DIRECTORY / "ledger.json"
    with locked(DIRECTORY.parent / "google-compatible-text-verification/stage"), locked(path):
        historical = HISTORICAL.read_bytes()
        ledger = DiagnosticLedger(path, historical)
        keys = fetch_project_credentials(secret_ref)
        for i in range(1, 6):
            project = f"project-{i}"
            for surface in ("native", "nonstream", "stream"):
                if ledger.data["halted"]:
                    break
                if (
                    surface == "stream"
                    and ledger.data["attempts"]
                    .get(f"g38-nonstream-{project}", {})
                    .get("result", {})
                    .get("status")
                    != "passed"
                ):
                    break
                assert HISTORICAL.read_bytes() == historical
                case = f"g38-{surface}-{project}"
                started = time.monotonic()
                if surface == "native":
                    result, observation = await native_case(keys[i - 1], ledger, project, case)
                else:
                    observer = ObservingTransport(
                        httpx.AsyncHTTPTransport(retries=0, trust_env=False), ledger, project, case
                    )
                    result = await run_compatible_case(
                        credential=keys[i - 1],
                        ledger=ledger,
                        project=project,
                        case_id=case,
                        transport=observer,
                        stream=surface == "stream",
                        model=MODEL,
                        case_timeout_seconds=MAX_LOGICAL_SECONDS,
                    )
                    observation = observer.observation
                result["elapsed_seconds"] = round(time.monotonic() - started, 3)
                ledger.finish(case, result, observation)
        assert HISTORICAL.read_bytes() == historical
        return ledger.data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--keyvault-ref")
    args = parser.parse_args()
    if not args.execute or not args.keyvault_ref:
        return 2
    logging.disable(logging.CRITICAL)
    try:
        data = asyncio.run(execute(args.keyvault_ref))
    except (ValueError, OSError, RuntimeError, httpx.HTTPError, TimeoutError):
        print(json.dumps({"status": "refused_or_interrupted"}))
        return 2
    print(json.dumps(data, indent=2))
    return int(data["halted"])


if __name__ == "__main__":
    raise SystemExit(main())
