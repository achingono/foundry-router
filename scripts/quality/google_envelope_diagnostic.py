"""One redacted structural observation of an exact compatible provider response."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging

import httpx
from google_compatible_runtime import INITIAL_USD, CompatibleGuard, run_compatible_case
from google_compatible_stage import LEDGER_PATH, MAX_RESULTS_BYTES, PROJECT_COUNT, STAGE_DIR
from google_live_budget import BudgetLedger, locked, write_atomic
from google_live_execute import fetch_project_credentials

from foundry_router.api.adapters.google_schema import load_bounded_json

DIAGNOSTIC_DIR = STAGE_DIR.parent / "google-compatible-envelope"
CASE_ID = "d08n-txt-gemini-3.5-flash-lite-project-2"
FIELDS = {
    "role",
    "content",
    "tool_calls",
    "refusal",
    "annotations",
    "reasoning_content",
    "reasoning",
    "audio",
    "images",
    "function_call",
    "extra_content",
}
MAX_SCHEMA_COUNT = 128
WRAPPERS = {"google", "gemini"}
SIGNATURES = {"thought_signature", "thoughtSignature", "signature"}
SMALL_SIGNATURE = 256
MEDIUM_SIGNATURE = 4096
MAX_SIGNATURE = 65536
LENGTH_CLASSES = {"empty", "small", "medium", "large", "over_bound"}


def shape(value):
    kind = (
        "null"
        if value is None
        else "bool"
        if type(value) is bool
        else "int"
        if type(value) is int
        else "float"
        if type(value) is float
        else "string"
        if isinstance(value, str)
        else "list"
        if isinstance(value, list)
        else "object"
        if isinstance(value, dict)
        else "other"
    )
    return {
        "type": kind,
        "null": value is None,
        "empty": isinstance(value, (str, list, dict)) and len(value) == 0,
    }


def signature_shape(value):
    result = shape(value)
    if isinstance(value, str):
        size = len(value.encode())
        result["length_class"] = (
            "empty"
            if size == 0
            else "small"
            if size <= SMALL_SIGNATURE
            else "medium"
            if size <= MEDIUM_SIGNATURE
            else "large"
            if size <= MAX_SIGNATURE
            else "over_bound"
        )
    return result


def wrapper_schema(extra):
    if not isinstance(extra, dict):
        return {"object": False}
    result = {
        "object": True,
        "unknown_count": min(len(extra.keys() - WRAPPERS), MAX_SCHEMA_COUNT),
        "wrappers": {},
    }
    for name in sorted(extra.keys() & WRAPPERS):
        value = extra[name]
        entry = {"shape": shape(value)}
        if isinstance(value, dict):
            entry["unknown_count"] = min(len(value.keys() - SIGNATURES), MAX_SCHEMA_COUNT)
            entry["signatures"] = {
                key: signature_shape(value[key]) for key in sorted(value.keys() & SIGNATURES)
            }
        result["wrappers"][name] = entry
    return result


def observe_schema(wire):
    try:
        data = load_bounded_json(wire.decode(), max_bytes=4 * 1024 * 1024)
    except (ValueError, UnicodeError):
        return {"valid_json": False}
    if not isinstance(data, dict):
        return {"valid_json": True, "top_object": False}
    choices = data.get("choices")
    result = {
        "valid_json": True,
        "top_object": True,
        "choices": shape(choices),
        "choice_count": min(len(choices), MAX_SCHEMA_COUNT) if isinstance(choices, list) else 0,
    }
    if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
        return result
    choice = choices[0]
    message = choice.get("message")
    result["message"] = shape(message)
    result["finish_reason"] = shape(choice.get("finish_reason"))
    result["finish_stop"] = choice.get("finish_reason") == "stop"
    if isinstance(message, dict):
        result["message_fields"] = {
            name: shape(message[name]) for name in sorted(FIELDS & message.keys())
        }
        if "extra_content" in message:
            result["extra_wrapper"] = wrapper_schema(message["extra_content"])
        result["other_message_field_count"] = min(len(message.keys() - FIELDS), MAX_SCHEMA_COUNT)
    return result


class ObserverGuard(CompatibleGuard):
    def _capture_usage(self, wire):
        super()._capture_usage(wire)
        self.safe_schema = observe_schema(wire)


async def run_diagnostic_case(**kwargs):
    observed = []

    def factory(*args, **inputs):
        guard = ObserverGuard(*args, **inputs)
        observed.append(guard)
        return guard

    result = await run_compatible_case(**kwargs, guard_factory=factory)
    result["safe_schema"] = getattr(observed[0], "safe_schema", {"observed": False})
    return result


def validate_result(result, ledger_case, *, case_id=CASE_ID, project="project-2"):
    allowed = {
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
        "safe_schema",
    }
    if (
        not isinstance(result, dict)
        or set(result) != allowed
        or result["case_id"] != case_id
        or result["project"] != project
        or result["model"] != "gemini-3.5-flash-lite"
        or result["surface"] != "openai_compat"
        or result["stream"] is not False
        or result["thinking_policy"] != "provider_default"
        or result["status"] not in {"passed", "failed"}
        or result["error_category"] not in {None, "provider_or_protocol_failure"}
    ):
        raise ValueError("Invalid diagnostic identity")
    for name in (
        "dispatched",
        "budget_overrun",
        "public_completed",
        "public_text_present",
        "usage_matches",
        "settlement_matches",
        "reservations_cleared",
    ):
        if type(result[name]) is not bool:
            raise ValueError("Invalid diagnostic flags")
    for name in (
        "http_status",
        "provider_http_status",
        "actual_tokens",
        "input_tokens",
        "output_tokens",
        "thought_tokens",
    ):
        if result[name] is not None and (type(result[name]) is not int or result[name] < 0):
            raise ValueError("Invalid diagnostic numbers")
    if (
        type(result["synthetic_debit_usd"]) not in {int, float}
        or not 0 <= result["synthetic_debit_usd"] <= INITIAL_USD
    ):
        raise ValueError("Invalid diagnostic debit")
    if result["dispatched"] and (
        ledger_case is None or ledger_case["actual_tokens"] != result["actual_tokens"]
    ):
        raise ValueError("Invalid diagnostic ledger binding")
    validate_schema(result["safe_schema"])
    return result


def validate_schema(schema):
    if not isinstance(schema, dict) or set(schema) - {
        "observed",
        "valid_json",
        "top_object",
        "choices",
        "choice_count",
        "message",
        "finish_reason",
        "finish_stop",
        "message_fields",
        "other_message_field_count",
        "extra_wrapper",
    }:
        raise ValueError("Invalid diagnostic schema")
    for name, value in schema.items():
        if name in {"observed", "valid_json", "top_object", "finish_stop"}:
            if type(value) is not bool:
                raise ValueError("Invalid schema flags")
        elif name in {"choice_count", "other_message_field_count"}:
            if type(value) is not int or not 0 <= value <= MAX_SCHEMA_COUNT:
                raise ValueError("Invalid schema count")
        elif name == "extra_wrapper":
            validate_wrapper(value)
        elif name == "message_fields":
            if not isinstance(value, dict) or set(value) - FIELDS:
                raise ValueError("Invalid schema field")
            for item in value.values():
                validate_shape(item)
        else:
            validate_shape(value)


def validate_wrapper(value):
    if value == {"object": False}:
        return
    if (
        not isinstance(value, dict)
        or set(value) != {"object", "unknown_count", "wrappers"}
        or value["object"] is not True
        or type(value["unknown_count"]) is not int
        or not 0 <= value["unknown_count"] <= MAX_SCHEMA_COUNT
        or not isinstance(value["wrappers"], dict)
        or set(value["wrappers"]) - WRAPPERS
    ):
        raise ValueError("Invalid extra wrapper")
    for entry in value["wrappers"].values():
        if not isinstance(entry, dict) or set(entry) not in (
            {"shape"},
            {"shape", "unknown_count", "signatures"},
        ):
            raise ValueError("Invalid wrapper fields")
        validate_shape(entry["shape"])
        if "signatures" not in entry:
            continue
        if (
            type(entry["unknown_count"]) is not int
            or not 0 <= entry["unknown_count"] <= MAX_SCHEMA_COUNT
            or not isinstance(entry["signatures"], dict)
            or set(entry["signatures"]) - SIGNATURES
        ):
            raise ValueError("Invalid signature fields")
        for signature in entry["signatures"].values():
            if not isinstance(signature, dict):
                raise TypeError("Invalid signature shape")
            base = {key: val for key, val in signature.items() if key != "length_class"}
            validate_shape(base)
            if set(signature) - {"type", "null", "empty", "length_class"} or (
                "length_class" in signature and signature["length_class"] not in LENGTH_CLASSES
            ):
                raise ValueError("Invalid signature length class")


def validate_shape(value):
    if (
        not isinstance(value, dict)
        or set(value) != {"type", "null", "empty"}
        or value["type"]
        not in {"null", "bool", "int", "float", "string", "list", "object", "other"}
        or type(value["null"]) is not bool
        or type(value["empty"]) is not bool
    ):
        raise ValueError("Invalid schema type flags")


def execute_diagnostic(  # noqa: PLR0913 -- fixed phase inputs and isolated test injection
    secret_ref,
    *,
    directory=DIAGNOSTIC_DIR,
    ledger_path=LEDGER_PATH,
    keys=None,
    transport_factory=None,
    case_id=CASE_ID,
    project="project-2",
    baseline_name="ledger-baseline.json",
    result_name="diagnostic-result.json",
):
    with locked(STAGE_DIR / "stage"):
        if not ledger_path.exists():
            raise ValueError("Existing ledger required")
        baseline = load_bounded_json(
            (directory / baseline_name).read_text(), max_bytes=MAX_RESULTS_BYTES
        )
        ledger = BudgetLedger(ledger_path)
        current = ledger._read()
        for owner, old in baseline["projects"].items():
            now = current["projects"][owner]
            allowed = {case_id} if owner == project else set()
            if (
                any(now["cases"].get(case) != value for case, value in old["cases"].items())
                or set(now["cases"]) - set(old["cases"]) - allowed
            ):
                raise ValueError("Historical ledger mismatch")
        path = directory / result_name
        if path.exists():
            return validate_result(
                load_bounded_json(path.read_text(), max_bytes=MAX_RESULTS_BYTES),
                current["projects"][project]["cases"].get(case_id),
                case_id=case_id,
                project=project,
            )
        if case_id in current["projects"][project]["cases"]:
            return {"case_id": case_id, "status": "ambiguous_consumed", "dispatched": True}
        if not ledger.can_reserve(project, 1088):
            raise ValueError("Diagnostic budget unavailable")
        credentials = keys if keys is not None else fetch_project_credentials(secret_ref)
        if len(credentials) != PROJECT_COUNT:
            raise ValueError("Invalid credential roster")
        factory = transport_factory or (
            lambda: httpx.AsyncHTTPTransport(trust_env=False, retries=0)
        )
        result = asyncio.run(
            run_diagnostic_case(
                credential=credentials[int(project[-1]) - 1],
                ledger=ledger,
                project=project,
                case_id=case_id,
                transport=factory(),
                stream=False,
            )
        )
        validate_result(
            result,
            ledger._read()["projects"][project]["cases"].get(case_id),
            case_id=case_id,
            project=project,
        )
        write_atomic(path, result)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--wrapper-followup", action="store_true")
    parser.add_argument("--keyvault-ref")
    args = parser.parse_args()
    if not args.execute or not args.keyvault_ref:
        return 2
    logging.disable(logging.CRITICAL)
    try:
        result = (
            execute_diagnostic(
                args.keyvault_ref,
                case_id="d08n-wrapper-gemini-3.5-flash-lite-project-3",
                project="project-3",
                baseline_name="ledger-baseline-followup.json",
                result_name="wrapper-result.json",
            )
            if args.wrapper_followup
            else execute_diagnostic(args.keyvault_ref)
        )
    except (ValueError, OSError, RuntimeError):
        print(json.dumps({"status": "refused_or_interrupted"}))
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
