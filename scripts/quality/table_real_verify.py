"""Four fixed Azure Responses cases with durable spend and incremental SSE bounds."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import math
import re
import time
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from google_live_budget import locked, write_atomic
from google_live_execute import fetch_credential
from table_real_prepare import MAX_ESTIMATE_USD, PRIVATE_PATH

from foundry_router.api.adapters.google_schema import load_bounded_json

DIRECTORY = Path(__file__).resolve().parents[2] / "docs/plans/table-real-inference"
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
MAX_FRAME_BYTES = 1024 * 1024
MAX_LEDGER_BYTES = 65536
DEADLINE_SECONDS = 30
SETTLEMENT_HEADROOM_SECONDS = 5
MAX_OUTPUT = 1024
MAX_INPUT = 64
MAX_TOTAL = MAX_OUTPUT + MAX_INPUT
HTTP_OK = 200
MIN_HTTP_STATUS = 100
MAX_HTTP_STATUS = 599
MODEL_COUNT = 2
CASE_COUNT = 4
MAX_LABEL_CHARS = 256
SETTLEMENT_TOLERANCE = 0.000002
PROMPT = "Reply with one short word."
RESULT_KEYS = {
    "status",
    "http_status",
    "completed",
    "text_present",
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "estimated_debit_usd",
    "settlement_matches",
    "reservations_cleared",
    "overrun",
    "elapsed_seconds",
}


def usage_values(usage):
    if not isinstance(usage, dict):
        raise ValueError("Missing usage")  # noqa: TRY004 -- sanitized protocol failure
    input_tokens, output_tokens = usage.get("input_tokens"), usage.get("output_tokens")
    if type(input_tokens) is not int or type(output_tokens) is not int:
        raise ValueError("Invalid usage")
    if input_tokens < 0 or output_tokens < 0:
        raise ValueError("Invalid usage")
    total = usage.get("total_tokens")
    if type(total) is not int or total != input_tokens + output_tokens:
        raise ValueError("Invalid total usage")
    return input_tokens, output_tokens, total


def text_present(body):
    output = body.get("output", [])
    return isinstance(output, list) and any(
        isinstance(item, dict)
        and isinstance(item.get("content"), list)
        and any(
            isinstance(part, dict)
            and part.get("type") == "output_text"
            and isinstance(part.get("text"), str)
            and bool(part["text"].strip())
            for part in item["content"]
        )
        for item in output
    )


class ResponseObservation:
    """Retain numeric maximums and flags; never retain response content in evidence."""

    def __init__(self):
        self.buffer = bytearray()
        self.completed = False
        self.text = False
        self.input_tokens = None
        self.output_tokens = None
        self.total_tokens = None
        self.usage = None
        self.invalid = False

    def observe_usage(self, usage):
        for field, attribute in (
            ("input_tokens", "input_tokens"),
            ("output_tokens", "output_tokens"),
            ("total_tokens", "total_tokens"),
        ):
            value = usage.get(field)
            if type(value) is int and value >= 0:
                setattr(self, attribute, max(getattr(self, attribute) or 0, value))
            elif value is not None:
                self.invalid = True

    def observe(self, data):
        if not isinstance(data, dict):
            raise ValueError("Invalid response")  # noqa: TRY004 -- sanitized protocol failure
        if isinstance(data.get("usage"), dict):
            self.observe_usage(data["usage"])
        if data.get("type") == "response.output_text.delta":
            self.text |= isinstance(data.get("delta"), str) and bool(data["delta"].strip())
        response = data.get("response") if isinstance(data.get("response"), dict) else data
        if isinstance(response.get("usage"), dict):
            self.observe_usage(response["usage"])
        if response.get("status") == "completed":
            if self.completed:
                raise ValueError("Duplicate terminal response")
            self.completed = True
            self.text |= text_present(response)
            self.usage = usage_values(response.get("usage"))
        if data.get("type") in {"error", "response.failed", "response.incomplete"}:
            raise ValueError("Failed response")

    def feed(self, chunk):
        self.buffer.extend(chunk)
        while True:
            # Preserve both supported SSE line ending conventions.
            indices = [(self.buffer.find(mark), mark) for mark in (b"\n\n", b"\r\n\r\n")]
            indices = [(index, mark) for index, mark in indices if index >= 0]
            if not indices:
                if len(self.buffer) > MAX_FRAME_BYTES:
                    raise ValueError("Frame bound exceeded")
                return
            index, mark = min(indices, key=lambda pair: pair[0])
            if index > MAX_FRAME_BYTES:
                raise ValueError("Frame bound exceeded")
            frame = bytes(self.buffer[:index])
            del self.buffer[: index + len(mark)]
            payload = b"\n".join(
                line[5:].lstrip(b" ") for line in frame.splitlines() if line.startswith(b"data:")
            )
            if payload and payload != b"[DONE]":
                self.observe(load_bounded_json(payload.decode(), max_bytes=MAX_FRAME_BYTES))

    def accepted(self):
        return (
            not self.invalid
            and not self.buffer.strip()
            and self.completed
            and self.text
            and self.usage is not None
            and self.usage == (self.input_tokens, self.output_tokens, self.total_tokens)
            and self.input_tokens <= MAX_INPUT
            and self.output_tokens <= MAX_OUTPUT
            and self.total_tokens <= MAX_TOTAL
        )


async def bounded_get(client, url, headers):
    async with asyncio.timeout(10):
        async with client.stream("GET", url, headers=headers) as response:
            if response.status_code != HTTP_OK:
                raise ValueError("Status unavailable")
            payload = bytearray()
            async for chunk in response.aiter_bytes():
                payload.extend(chunk)
                if len(payload) > MAX_FRAME_BYTES:
                    raise ValueError("Status bound exceeded")
            return load_bounded_json(payload.decode(), max_bytes=MAX_FRAME_BYTES)


def snapshot(data, models):
    if not isinstance(data, dict) or data.get("model_aliases") not in ({}, None):
        raise ValueError("Status contract mismatch")
    if data.get("config", {}).get("retry_attempts") != 0:
        raise ValueError("Retries must be disabled")
    result = {}
    for model in models:
        pool = data["models"][model["model"]]["backends"]
        if set(pool) != {model["backend"]}:
            raise ValueError("Single exact backend required")
        live = data["backends"][model["backend"]]["live"]
        amount = live["estimated_remaining_usd"]
        if type(amount) not in {int, float} or not math.isfinite(amount) or amount < 0:
            raise ValueError("Invalid estimate")
        if live["active_reservations"] != 0 or live["reserved_inflight_usd"] != 0:
            raise ValueError("Reservations not cleared")
        result[model["backend"]] = {
            "remaining": amount,
            "cycle": live["current_cycle_start_utc"],
        }
    return result


async def _run_case(  # noqa: PLR0912, PLR0913, PLR0917 -- fixed verifier contract
    client, origin, client_key, admin_key, model, stream, models, persist=None
):
    started = time.monotonic()
    observer = ResponseObservation()
    result = {
        "status": "failed",
        "http_status": None,
        "completed": False,
        "text_present": False,
        "input_tokens": None,
        "output_tokens": None,
        "total_tokens": None,
        "estimated_debit_usd": None,
        "settlement_matches": False,
        "reservations_cleared": False,
        "overrun": False,
        "elapsed_seconds": 0,
    }
    before = snapshot(
        await bounded_get(client, origin + "/admin/status", {"x-admin-key": admin_key}), models
    )
    try:
        async with asyncio.timeout_at(started + DEADLINE_SECONDS - SETTLEMENT_HEADROOM_SECONDS):
            body = {
                "model": model["model"],
                "input": PROMPT,
                "max_output_tokens": MAX_OUTPUT,
                "stream": stream,
            }
            async with client.stream(
                "POST",
                origin + "/openai/v1/responses",
                headers={"Authorization": "Bearer " + client_key},
                json=body,
            ) as response:
                result["http_status"] = int(response.status_code)
                if response.status_code != HTTP_OK:
                    raise ValueError("Inference unsuccessful")  # noqa: TRY301 -- protocol guard
                total = 0
                payload = bytearray()
                async for chunk in response.aiter_bytes():
                    total += len(chunk)
                    if total > MAX_RESPONSE_BYTES:
                        raise ValueError("Response bound exceeded")  # noqa: TRY301 -- byte guard
                    if stream:
                        observer.feed(chunk)
                    else:
                        payload.extend(chunk)
                if not stream:
                    observer.observe(
                        load_bounded_json(payload.decode(), max_bytes=MAX_RESPONSE_BYTES)
                    )
                if not observer.accepted():
                    raise ValueError("Incomplete response evidence")  # noqa: TRY301 -- terminal guard
    except (ValueError, httpx.HTTPError, TimeoutError):
        observer.invalid = True
    result.update(
        completed=observer.completed,
        text_present=observer.text,
        input_tokens=observer.input_tokens,
        output_tokens=observer.output_tokens,
        total_tokens=observer.total_tokens,
    )
    if observer.input_tokens is not None or observer.output_tokens is not None:
        debit = (
            (observer.input_tokens or 0) * model["input_per_million"]
            + (observer.output_tokens or 0) * model["output_per_million"]
        ) / 1_000_000
        result["estimated_debit_usd"] = debit
        result["overrun"] = (
            (observer.input_tokens or 0) > MAX_INPUT
            or (observer.output_tokens or 0) > MAX_OUTPUT
            or debit > model["reserve_usd"]
        )
    result["overrun"] |= (
        (observer.total_tokens or 0) > MAX_TOTAL
        or (observer.input_tokens or 0) > MAX_INPUT
        or (observer.output_tokens or 0) > MAX_OUTPUT
    )
    if result["overrun"]:
        # Unknown split of an independently reported total uses the highest token price.
        result["estimated_debit_usd"] = max(
            result["estimated_debit_usd"] or 0,
            (observer.total_tokens or 0)
            * max(model["input_per_million"], model["output_per_million"])
            / 1_000_000,
        )
    result["elapsed_seconds"] = round(time.monotonic() - started, 3)
    if persist is not None:
        persist(result.copy())
    try:
        after = snapshot(
            await bounded_get(client, origin + "/admin/status", {"x-admin-key": admin_key}), models
        )
        result["reservations_cleared"] = True
        backend = model["backend"]
        debit = result["estimated_debit_usd"]
        result["settlement_matches"] = (
            debit is not None
            and before[backend]["cycle"] == after[backend]["cycle"]
            and abs(before[backend]["remaining"] - after[backend]["remaining"] - debit)
            <= SETTLEMENT_TOLERANCE
            and all(before[other] == after[other] for other in before if other != backend)
        )
    except (ValueError, KeyError, httpx.HTTPError, TimeoutError):
        pass
    if (
        observer.accepted()
        and result["settlement_matches"]
        and result["reservations_cleared"]
        and not result["overrun"]
    ):
        result["status"] = "passed"
    result["elapsed_seconds"] = round(time.monotonic() - started, 3)
    return result


async def run_case(  # noqa: PLR0913, PLR0917 -- fixed verifier contract
    client, origin, client_key, admin_key, model, stream, models, persist=None
):
    async with asyncio.timeout(DEADLINE_SECONDS):
        return await _run_case(
            client, origin, client_key, admin_key, model, stream, models, persist
        )


def validate_origin(origin):
    parts = urlsplit(origin)
    if (
        parts.scheme != "https"
        or not parts.hostname
        or not parts.hostname.endswith(".azurecontainerapps.io")
        or parts.username
        or parts.password
        or parts.port
        or parts.path not in {"", "/"}
        or parts.query
        or parts.fragment
    ):
        raise ValueError("Exact Azure test origin required")
    return origin.rstrip("/")


def validate_ledger(data, private):  # noqa: PLR0912 -- strict evidence boundary checks
    if (
        not isinstance(data, dict)
        or set(data) != {"fingerprint", "cases"}
        or data["fingerprint"] != private["config_fingerprint"]
        or not isinstance(data["cases"], dict)
    ):
        raise ValueError("Ledger contract mismatch")
    allowed = {
        f"{model['label']}-{'stream' if stream else 'nonstream'}": model
        for model in private["models"]
        for stream in (False, True)
    }
    for case, item in data["cases"].items():
        if (
            case not in allowed
            or not isinstance(item, dict)
            or set(item) != {"reserved_usd", "result"}
            or item["reserved_usd"] != allowed[case]["reserve_usd"]
        ):
            raise ValueError("Invalid case ledger")
        result = item["result"]
        if result is not None:
            if (
                not isinstance(result, dict)
                or set(result) != RESULT_KEYS
                or result["status"] not in {"passed", "failed"}
            ):
                raise ValueError("Invalid result envelope")
            for flag in (
                "completed",
                "text_present",
                "settlement_matches",
                "reservations_cleared",
                "overrun",
            ):
                if type(result[flag]) is not bool:
                    raise ValueError("Invalid result flag")
            for count in (
                "http_status",
                "input_tokens",
                "output_tokens",
                "total_tokens",
                "estimated_debit_usd",
                "elapsed_seconds",
            ):
                value = result[count]
                if value is not None and (
                    type(value) not in {int, float} or not math.isfinite(value) or value < 0
                ):
                    raise ValueError("Invalid result number")
            for count in ("http_status", "input_tokens", "output_tokens", "total_tokens"):
                if result[count] is not None and type(result[count]) is not int:
                    raise ValueError("Integer result counts required")
            if result["elapsed_seconds"] is None or result["elapsed_seconds"] > DEADLINE_SECONDS:
                raise ValueError("Invalid case elapsed bound")
            if (
                result["http_status"] is not None
                and not MIN_HTTP_STATUS <= result["http_status"] <= MAX_HTTP_STATUS
            ):
                raise ValueError("Invalid HTTP status bound")
            if result["status"] == "passed":
                validate_passed(result, allowed[case])
            if case.endswith("-stream"):
                prior = data["cases"].get(case.replace("-stream", "-nonstream"), {}).get("result")
                if prior is None or prior["status"] != "passed":
                    raise ValueError("Stream requires passing nonstream result")
    return data


def validate_passed(result, model):
    if (
        not all(
            result[flag]
            for flag in ("completed", "text_present", "settlement_matches", "reservations_cleared")
        )
        or result["overrun"]
        or result["http_status"] != HTTP_OK
    ):
        raise ValueError("Invalid passing flags")
    inputs, outputs, total = result["input_tokens"], result["output_tokens"], result["total_tokens"]
    if any(type(value) is not int for value in (inputs, outputs, total)):
        raise ValueError("Passing counts required")
    if inputs > MAX_INPUT or outputs > MAX_OUTPUT or total != inputs + outputs or total > MAX_TOTAL:
        raise ValueError("Invalid passing usage")
    expected = (
        inputs * model["input_per_million"] + outputs * model["output_per_million"]
    ) / 1_000_000
    if result["estimated_debit_usd"] != expected:
        raise ValueError("Invalid passing debit")


def validate_private(private, origin):  # noqa: PLR0912 -- exact private contract checks
    if not isinstance(private, dict) or set(private) != {
        "origin",
        "config_fingerprint",
        "models",
        "client_secret_ref",
        "admin_secret_ref",
        "deployment_fingerprint",
    }:
        raise ValueError("Exact private deployment contract required")
    for name in ("config_fingerprint", "deployment_fingerprint"):
        if not isinstance(private[name], str) or not re.fullmatch(r"[a-f0-9]{64}", private[name]):
            raise ValueError("Bounded deployment fingerprint required")
    from table_real_prepare import validate_pinned  # noqa: PLC0415 -- shared CLI boundary

    for name in ("client_secret_ref", "admin_secret_ref"):
        validate_pinned(private[name], {"id": private[name]})
    if private.get("origin") != origin:
        raise ValueError("Origin must match discovered isolated deployment")
    if len(private.get("models", [])) != MODEL_COUNT:
        raise ValueError("Two exact models required")
    labels = set()
    for model in private["models"]:
        if (
            not isinstance(model, dict)
            or set(model)
            != {
                "label",
                "model",
                "backend",
                "reserve_usd",
                "input_per_million",
                "output_per_million",
            }
            or model["label"] not in {"model-1", "model-2"}
            or model["label"] in labels
        ):
            raise ValueError("Invalid model contract")
        labels.add(model["label"])
        for name in ("model", "backend"):
            if (
                not isinstance(model[name], str)
                or not model[name]
                or len(model[name]) > MAX_LABEL_CHARS
            ):
                raise ValueError("Invalid model binding")
        for name in ("reserve_usd", "input_per_million", "output_per_million"):
            value = model[name]
            if type(value) not in {int, float} or not math.isfinite(value) or value < 0:
                raise ValueError("Invalid price bound")
        expected = (
            MAX_INPUT * model["input_per_million"] + MAX_OUTPUT * model["output_per_million"]
        ) / 1_000_000
        if model["reserve_usd"] != expected:
            raise ValueError("Reservation does not match maximum usage")
    if sum(model["reserve_usd"] * 2 for model in private["models"]) > MAX_ESTIMATE_USD:
        raise ValueError("Authorized maximum estimate exceeded")


async def execute(private, origin, keys, path, transport=None):
    validate_private(private, origin)
    with locked(path):
        if path.exists():
            data = validate_ledger(
                load_bounded_json(path.read_text(), max_bytes=MAX_LEDGER_BYTES), private
            )
        else:
            data = {"fingerprint": private["config_fingerprint"], "cases": {}}
            write_atomic(path, data)
        async with httpx.AsyncClient(
            transport=transport, trust_env=False, follow_redirects=False, timeout=10
        ) as client:
            for model in private["models"]:
                for stream in (False, True):
                    case = f"{model['label']}-{'stream' if stream else 'nonstream'}"
                    if case in data["cases"]:
                        prior = data["cases"][case]["result"]
                        if prior is None or prior["status"] != "passed":
                            break
                        continue
                    # Any ambiguous previous dispatch prevents further provider traffic.
                    if any(item["result"] is None for item in data["cases"].values()):
                        return data
                    if any(
                        item["result"] is not None and item["result"]["overrun"]
                        for item in data["cases"].values()
                    ):
                        return data
                    spent = sum(
                        max(
                            item["reserved_usd"],
                            (item["result"] or {}).get("estimated_debit_usd") or 0,
                        )
                        for item in data["cases"].values()
                    )
                    if spent + model["reserve_usd"] > MAX_ESTIMATE_USD:
                        return data
                    # Persist before any awaited operation that can send inference traffic.
                    data["cases"][case] = {"reserved_usd": model["reserve_usd"], "result": None}
                    write_atomic(path, data)

                    def persist(observed, current_case=case):
                        data["cases"][current_case]["result"] = observed
                        validate_ledger(data, private)
                        write_atomic(path, data)

                    try:
                        result = await run_case(
                            client,
                            origin,
                            keys[0],
                            keys[1],
                            model,
                            stream,
                            private["models"],
                            persist,
                        )
                    except (ValueError, KeyError, httpx.HTTPError, TimeoutError):
                        break
                    data["cases"][case]["result"] = result
                    validate_ledger(data, private)
                    write_atomic(path, data)
                    if result["status"] != "passed":
                        break
        return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--origin", required=True)
    args = parser.parse_args()
    if not args.execute:
        return 2
    logging.disable(logging.CRITICAL)
    try:
        origin = validate_origin(args.origin)
        private = load_bounded_json(PRIVATE_PATH.read_text(), max_bytes=MAX_LEDGER_BYTES)
        validate_private(private, origin)
        from table_real_binding import bind_live  # noqa: PLC0415 -- CLI-only Azure discovery

        bind_live(private, origin)
        keys = [
            json.loads(fetch_credential(private[key]))[0]
            for key in ("client_secret_ref", "admin_secret_ref")
        ]
        data = asyncio.run(execute(private, origin, keys, DIRECTORY / "ledger.json"))
        print(json.dumps(data, indent=2))
    except (OSError, ValueError, KeyError, httpx.HTTPError):
        print(json.dumps({"status": "refused_or_interrupted"}))
        return 2
    return int(
        len(data["cases"]) != CASE_COUNT
        or any(
            item["result"] is None or item["result"]["status"] != "passed"
            for item in data["cases"].values()
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
