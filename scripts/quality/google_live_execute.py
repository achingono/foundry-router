"""Guarded live execution for reviewer-approved native text cases.

Dry-run validation never imports this module. Execution requires explicit
``--execute`` plus ``--keyvault-ref`` plus ``--ledger``; anything else fails
closed with zero provider requests. Only ``text_nonstream`` rows carrying the
``docs_supported_pending_live`` status are dispatchable; every other row is
skipped with a recorded reason and causes no request.

Capability notes: streaming, tools and media rows are never selected here even
if marked executable — they need their own reviewed execution contracts first.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
from pathlib import Path
from typing import Any

import httpx
from google_live_budget import BudgetLedger
from google_live_runtime import (
    LEVEL_OUTPUT_TOKENS,
    LEVEL_RESERVED_TOKENS,
    MAX_PROMPT_CHARS,
    OUTPUT_TOKENS,
    RESERVED_TOKENS,
    run_text_case,
)
from google_live_runtime import PROMPT as DEFAULT_PROMPT

from foundry_router.api.adapters.google_schema import load_bounded_json

EXECUTABLE_CAPABILITY = "text_nonstream"
EXECUTABLE_STATUS = "docs_supported_pending_live"
PRIORITY_MODELS = [
    "models/gemini-2.5-flash-lite",
    "models/gemini-2.5-flash",
]
LEVEL_BY_MODEL = {
    "models/gemini-3.5-flash-lite": "minimal",
    "models/gemini-3.8-flash": "low",
}
PROJECTS = [f"project-{index}" for index in range(1, 6)]
MAX_CASE_PREFIX_CHARS = 20
CREDENTIAL_TIMEOUT_SECONDS = 30
MAX_CREDENTIAL_BYTES = 8192
MAX_SECRET_REF_BYTES = 2048


def _native_model(exact_id: str) -> str:
    if not isinstance(exact_id, str):
        raise TypeError("Invalid exact model identifier")
    if not exact_id.startswith("models/"):
        raise ValueError("Invalid exact model identifier")
    native = exact_id.removeprefix("models/")
    if not native or "/" in native:
        raise ValueError("Invalid exact model identifier")
    return native


def select_cases(
    manifest: dict[str, Any],
    capability: str = EXECUTABLE_CAPABILITY,
    case_prefix: str = "",
) -> list[dict[str, str]]:
    """Return deterministic dispatchable cases, flash-lite first, per project.

    Only free-tier-evidenced rows whose requested capability status is exactly
    the executable status and whose methods include ``generateContent`` qualify.
    Anything else (tools, media, pending rows) is never selected.
    """
    if capability not in {"text_nonstream", "text_stream"}:
        raise ValueError("Unsupported validation capability")
    if case_prefix and (
        not isinstance(case_prefix, str)
        or len(case_prefix) > MAX_CASE_PREFIX_CHARS
        or not case_prefix.replace("-", "").replace("_", "").isalnum()
    ):
        raise ValueError("Invalid case prefix")
    if not isinstance(manifest, dict):
        raise TypeError("Invalid validation manifest")
    if not isinstance(manifest.get("models"), list):
        raise TypeError("Invalid validation manifest")
    by_id = {}
    for row in manifest["models"]:
        if isinstance(row, dict) and isinstance(row.get("id"), str):
            by_id[row["id"]] = row
    ordered = [mid for mid in PRIORITY_MODELS if mid in by_id]
    ordered.extend(sorted(mid for mid in by_id if mid not in PRIORITY_MODELS))
    cases = []
    for project in PROJECTS:
        for exact_id in ordered:
            row = by_id[exact_id]
            capabilities = row.get("capabilities")
            if (
                row.get("free_tier_text") is not True
                or row.get("pricing_evidence") != "https://ai.google.dev/gemini-api/docs/pricing"
                or not isinstance(capabilities, dict)
                or capabilities.get(capability) != EXECUTABLE_STATUS
                or "generateContent" not in (row.get("methods") or [])
            ):
                continue
            native = _native_model(exact_id)
            stem = f"txt-{native}-{project}"
            cases.append(
                {
                    "case_id": f"{case_prefix}-{stem}" if case_prefix else stem,
                    "model": exact_id,
                    "native_model": native,
                    "project": project,
                    "capability": capability,
                    "thinking_level": LEVEL_BY_MODEL.get(exact_id),
                }
            )
    return cases


def fetch_credential(secret_ref: str) -> str:
    """Capture one Key Vault secret value into memory via Azure CLI.

    The reference itself is caller-supplied and never logged; the value is
    never printed, never written, and only ever injected as an HTTPS header.
    Any failure (missing CLI, timeout, non-zero exit, empty output) fails
    closed before any ledger or provider activity.
    """
    if (
        not isinstance(secret_ref, str)
        or not secret_ref.strip()
        or len(secret_ref) > MAX_SECRET_REF_BYTES
    ):
        raise ValueError("Credential fetch failed")
    try:
        completed = subprocess.run(
            [
                "az",
                "keyvault",
                "secret",
                "show",
                "--id",
                secret_ref,
                "--query",
                "value",
                "-o",
                "tsv",
            ],
            capture_output=True,
            text=True,
            timeout=CREDENTIAL_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError("Credential fetch failed") from exc
    value = completed.stdout.strip()
    if completed.returncode != 0 or not value or len(value) > MAX_CREDENTIAL_BYTES:
        raise ValueError("Credential fetch failed")
    return value


def fetch_project_credentials(secret_ref: str) -> list[str]:
    """Parse the secret value as a JSON array of per-project API keys.

    The operator convention is index order: key ``i`` serves ``project-i``,
    keeping free-tier quota attribution per project. Length must match the
    project roster exactly; anything else fails closed before any ledger or
    provider activity. Key material is never logged or written.
    """
    raw = fetch_credential(secret_ref)
    try:
        parsed = load_bounded_json(raw, max_bytes=MAX_CREDENTIAL_BYTES)
    except (ValueError, TypeError):
        raise ValueError("Credential fetch failed") from None
    if (
        not isinstance(parsed, list)
        or len(parsed) != len(PROJECTS)
        or any(not isinstance(key, str) or not key.strip() for key in parsed)
    ):
        raise ValueError("Credential fetch failed")
    return list(parsed)


def _case_budget(case: dict[str, Any]) -> tuple[int, int]:
    if case.get("thinking_level") is not None:
        return LEVEL_OUTPUT_TOKENS, LEVEL_RESERVED_TOKENS
    return OUTPUT_TOKENS, RESERVED_TOKENS


async def _run_case(  # noqa: PLR0913 -- explicit owned validation inputs
    *,
    credential: str,
    case: dict[str, str],
    ledger: Any,
    transport: httpx.AsyncBaseTransport,
    prompt: str,
    stream: bool,
) -> dict[str, Any]:
    output_tokens, reserved_tokens = _case_budget(case)
    if not ledger.can_reserve(case["project"], reserved_tokens):
        return {**case, "status": "skipped", "reason": "project_budget_unavailable"}
    try:
        result = await run_text_case(
            credential=credential,
            model=case["native_model"],
            ledger=ledger,
            project=case["project"],
            case_id=case["case_id"],
            transport=transport,
            thinking_level=case.get("thinking_level"),
            output_tokens=output_tokens,
            reserved_tokens=reserved_tokens,
            prompt=prompt,
            stream=stream,
        )
    except (OSError, ValueError, RuntimeError, TimeoutError):
        return {**case, "status": "failed", "reason": "provider_error"}
    return {**case, **result}


def _known_shape(case: dict[str, Any]) -> bool:
    return case["model"] in PRIORITY_MODELS or case["model"] in LEVEL_BY_MODEL


def execute(  # noqa: PLR0913 -- explicit owned validation inputs
    *,
    manifest: dict[str, Any],
    keyvault_ref: str,
    ledger_path: Path,
    transport_factory: Any = None,
    case_id: str | None = None,
    capability: str = EXECUTABLE_CAPABILITY,
    case_prefix: str = "",
    prompt: str | None = None,
) -> tuple[dict[str, Any], int]:
    """Run dispatchable cases sequentially within ledger caps.

    Returns (summary, exit_code): 0 all passed, 1 completed with failures or
    skips, 2 refused before any provider request. No secrets in the summary.
    ``case_id`` optionally restricts the run to a single pilot case.
    """
    if capability not in {"text_nonstream", "text_stream"}:
        raise ValueError("Unsupported validation capability")
    prompt = DEFAULT_PROMPT if prompt is None else prompt
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > MAX_PROMPT_CHARS:
        return {
            "status": "invalid_prompt",
            "models": len(manifest.get("models", [])),
            "executable_cases": 0,
            "provider_requests": 0,
            "cases": [],
        }, 2
    stream = capability == "text_stream"
    cases = select_cases(manifest, capability=capability, case_prefix=case_prefix)
    if case_id is not None:
        cases = [case for case in cases if case["case_id"] == case_id]
    if not cases:
        return {
            "status": "no_executable_cases",
            "models": len(manifest.get("models", [])),
            "executable_cases": 0,
            "provider_requests": 0,
            "cases": [],
        }, 2
    try:
        credentials = fetch_project_credentials(keyvault_ref)
    except ValueError:
        return {
            "status": "credential_unavailable",
            "models": len(manifest.get("models", [])),
            "executable_cases": len(cases),
            "provider_requests": 0,
            "cases": [],
        }, 2
    try:
        ledger = BudgetLedger(ledger_path)
    except (OSError, ValueError):
        return {
            "status": "invalid_ledger",
            "models": len(manifest.get("models", [])),
            "executable_cases": len(cases),
            "provider_requests": 0,
            "cases": [],
        }, 2
    factory = transport_factory or httpx.AsyncHTTPTransport
    results = []
    dispatched = 0
    for case in cases:
        if not _known_shape(case):
            results.append({**case, "status": "skipped", "reason": "unsupported_thinking_shape"})
            continue
        transport = factory()
        result = asyncio.run(
            _run_case(
                credential=credentials[PROJECTS.index(case["project"])],
                case=case,
                ledger=ledger,
                transport=transport,
                prompt=prompt,
                stream=stream,
            )
        )
        public = {key: result[key] for key in sorted(result) if key != "credential"}
        results.append(public)
        if result.get("status") != "skipped" and result.get("dispatched"):
            dispatched += 1
        if result.get("budget_overrun"):
            continue
    summary = {
        "status": "completed",
        "models": len(manifest.get("models", [])),
        "executable_cases": len(cases),
        "provider_requests": dispatched,
        "passed": sum(1 for item in results if item.get("status") == "passed"),
        "failed": sum(1 for item in results if item.get("status") == "failed"),
        "skipped": sum(1 for item in results if item.get("status") == "skipped"),
        "cases": results,
    }
    code = 0 if summary["failed"] == 0 and summary["skipped"] == 0 else 1
    return summary, code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--keyvault-ref", required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--case-id", default=None)
    parser.add_argument("--capability", default=EXECUTABLE_CAPABILITY)
    parser.add_argument("--case-prefix", default="")
    parser.add_argument("--prompt", default=None)
    args = parser.parse_args(argv)
    try:
        manifest = load_bounded_json(args.manifest.read_text(), max_bytes=1048576)
        summary, code = execute(
            manifest=manifest,
            keyvault_ref=args.keyvault_ref,
            ledger_path=args.ledger,
            case_id=args.case_id,
            capability=args.capability,
            case_prefix=args.case_prefix,
            prompt=args.prompt,
        )
    except (OSError, ValueError, TypeError, KeyError):
        summary, code = {"status": "invalid_manifest", "provider_requests": 0}, 2
    print(json.dumps(summary, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
