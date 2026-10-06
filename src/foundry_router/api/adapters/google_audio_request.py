"""Versioned finite generated-audio request extension; no ordinary request interception."""

from __future__ import annotations

from typing import Any

AUDIO_REQUEST_FIELD = "foundry_audio_generation"
AUDIO_OUTPUT_FIELD = "foundry_generated_audio"
MAX_AUDIO_RESPONSE_BYTES = 700000
_ALLOWED = {
    "model",
    "input",
    "instructions",
    "metadata",
    "store",
    "stream",
    "max_output_tokens",
    AUDIO_REQUEST_FIELD,
}


def audio_output_request(body: dict[str, Any]) -> bool:
    return AUDIO_REQUEST_FIELD in body


def validate_audio_output_request(body: dict[str, Any], profile: Any) -> str:
    config = body.get(AUDIO_REQUEST_FIELD)
    bound = profile.generated_output_tokens_bound
    if (
        set(body) - _ALLOWED
        or "audio_output" not in profile.features
        or not isinstance(config, dict)
        or set(config) != {"version", "format", "voice"}
        or type(config.get("version")) is not int
        or config.get("version") != 1
        or config.get("format") != "wav"
        or not isinstance(config.get("voice"), str)
        or config["voice"] not in profile.audio_output_voices
        or body.get("stream", False) is not False
        or body.get("store", False) is not False
        or not isinstance(body.get("input"), str)
        or not body["input"].strip()
        or len(body["input"].encode()) > 4096
        or type(body.get("max_output_tokens", bound)) is not int
        or body.get("max_output_tokens", bound) != bound
    ):
        raise ValueError("Unsupported finite generated audio request")
    if "instructions" in body and (
        not isinstance(body["instructions"], str) or len(body["instructions"].encode()) > 1024
    ):
        raise ValueError("Invalid generated audio instructions")
    if "metadata" in body:
        metadata = body["metadata"]
        if (
            not isinstance(metadata, dict)
            or len(metadata) > 16
            or any(
                not isinstance(key, str)
                or len(key) > 64
                or not isinstance(value, str)
                or len(value) > 512
                for key, value in metadata.items()
            )
        ):
            raise ValueError("Invalid generated audio metadata")
    voice: str = config["voice"]
    return voice
