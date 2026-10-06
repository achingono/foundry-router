"""Opt-in isolated Google matrix validation. Dormant until exact protocol gates pass."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from google_live_budget import REQUEST_LIMIT, TOKEN_LIMIT

from foundry_router.api.adapters.google_schema import load_bounded_json

CATALOG = (
    Path(__file__).resolve().parents[2]
    / "docs/plans/google-ai-studio-tools-multimodal/live-discovery.json"
)

MAX_MODELS = 1000
MAX_MANIFEST_BYTES = 1048576

CAPABILITIES = {
    "text_nonstream",
    "text_stream",
    "tools",
    "structured_text",
    "image_input",
    "pdf_input",
    "wav_input",
    "avi_input",
    "image_output",
    "audio_output",
}
STATUSES = {
    "awaiting_exact_thinking_protocol_review",
    "unverified_free_tier_or_unsupported_transport",
    "pending_case",
    "pending_case_or_signed_startup_gate",
    "pending_codec_case",
    "code_gate_pending",
}


def _load_catalog(catalog_path: Path) -> dict[str, list[str]]:
    """Load the synthetic dormant catalog; any shape problem fails closed."""
    if catalog_path.stat().st_size > MAX_MANIFEST_BYTES:
        raise ValueError("Catalog bound exceeded")
    catalog = load_bounded_json(catalog_path.read_text(), max_bytes=MAX_MANIFEST_BYTES)
    if (
        not isinstance(catalog, dict)
        or not isinstance(catalog.get("projects"), list)
        or not catalog["projects"]
        or not isinstance(catalog["projects"][0], dict)
        or not isinstance(catalog["projects"][0].get("models"), list)
        or not 1 <= len(catalog["projects"][0]["models"]) <= MAX_MODELS
    ):
        raise ValueError("Invalid validation catalog")
    catalog_models: dict[str, list[str]] = {}
    for row in catalog["projects"][0]["models"]:
        if (
            not isinstance(row, dict)
            or not isinstance(row.get("id"), str)
            or not row["id"]
            or row["id"] in catalog_models
            or not isinstance(row.get("methods"), list)
            or not row["methods"]
            or any(not isinstance(method, str) or not method for method in row["methods"])
        ):
            raise ValueError("Invalid catalog model row")
        catalog_models[row["id"]] = list(row["methods"])
    return catalog_models


def validate_manifest(manifest: Any, *, catalog_path: Path = CATALOG) -> dict[str, Any]:
    if not isinstance(manifest, dict) or (
        manifest.get("version") != 1
        or manifest.get("max_requests_per_project") != REQUEST_LIMIT
        or manifest.get("max_tokens_per_project") != TOKEN_LIMIT
        or manifest.get("max_paid_spend_usd") != 0
        or manifest.get("initial_discovery_requests_per_project") != 1
        or not isinstance(manifest.get("models"), list)
        or not 1 <= len(manifest["models"]) <= MAX_MODELS
    ):
        raise ValueError("Invalid validation manifest")
    catalog_models = _load_catalog(catalog_path)
    if len(manifest["models"]) != len(catalog_models):
        raise ValueError("Invalid catalog coverage")
    seen = set()
    for row in manifest["models"]:
        if (
            not isinstance(row, dict)
            or not isinstance(row.get("id"), str)
            or row["id"] not in catalog_models
            or row["id"] in seen
            or not isinstance(row.get("methods"), list)
            or row["methods"] != catalog_models[row["id"]]
            or type(row.get("free_tier_text")) is not bool
            or not isinstance(row.get("capabilities"), dict)
            or set(row["capabilities"]) != CAPABILITIES
            or any(
                not isinstance(status, str) or status not in STATUSES
                for status in row["capabilities"].values()
            )
            or (
                row["free_tier_text"]
                and row.get("pricing_evidence") != "https://ai.google.dev/gemini-api/docs/pricing"
            )
        ):
            raise ValueError("Invalid model evidence row")
        seen.add(row["id"])
    return {
        "models": len(seen),
        "dispatch_eligible_cases": 0,
        "status": "protocol_gates_pending",
        "provider_requests": 0,
        "max_requests_per_project": REQUEST_LIMIT,
        "max_tokens_per_project": TOKEN_LIMIT,
        "max_paid_spend_usd": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, default=CATALOG)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    try:
        if args.manifest.stat().st_size > MAX_MANIFEST_BYTES:
            raise ValueError("Manifest bound exceeded")  # noqa: TRY301
        summary = validate_manifest(
            load_bounded_json(args.manifest.read_text(), max_bytes=MAX_MANIFEST_BYTES),
            catalog_path=args.catalog,
        )
        if args.execute:
            print(json.dumps({**summary, "execution": "rejected_missing_protocol_evidence"}))
            return 2
        print(json.dumps(summary, sort_keys=True))
        return 0  # noqa: TRY300
    except (OSError, ValueError, TypeError, KeyError):
        print(json.dumps({"status": "invalid_manifest", "provider_requests": 0}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
