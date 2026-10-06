"""Finite PCM WAV preparation; no codecs, transcoding, paths or network access."""

from __future__ import annotations

import base64
import binascii
import hashlib
import re
import struct
from dataclasses import dataclass
from typing import Any

from foundry_router.api.google_pdf import PdfPreparationError

PREFIX = "data:audio/wav;base64,"
MAX_BYTES = 320044


@dataclass(frozen=True, repr=False)
class PreparedAudio:
    position: tuple[int, int]
    digest: str
    decoded_bytes: int
    frames: int


def audio_parts(body: dict[str, Any]) -> list[tuple[tuple[int, int], dict[str, Any]]]:
    result: list[tuple[tuple[int, int], dict[str, Any]]] = []
    history = body.get("input")
    if not isinstance(history, list):
        return result
    if len(history) > 256:
        raise PdfPreparationError(422, "Audio history bound exceeded")
    for index, item in enumerate(history):
        if not isinstance(item, dict) or not isinstance(item.get("content"), list):
            continue
        if len(item["content"]) > 64:
            raise PdfPreparationError(422, "Audio content bound exceeded")
        for part_index, part in enumerate(item["content"]):
            if (
                isinstance(part, dict)
                and part.get("type") == "input_file"
                and isinstance(part.get("file_data"), str)
                and part["file_data"].startswith(PREFIX)
            ):
                if item.get("role") != "user" or len(result) >= 2:
                    raise PdfPreparationError(422, "Unsupported audio placement or count")
                result.append(((index, part_index), part))
    return result


def validate_audio_shape(part: dict[str, Any]) -> str:
    uri = part.get("file_data")
    if (
        set(part) - {"type", "filename", "file_data"}
        or not isinstance(uri, str)
        or not uri.startswith(PREFIX)
        or len(uri) > len(PREFIX) + 4 * ((MAX_BYTES + 2) // 3)
        or (
            "filename" in part
            and (
                not isinstance(part["filename"], str)
                or re.fullmatch(r"[A-Za-z0-9_.-]{1,60}\.wav", part["filename"]) is None
            )
        )
    ):
        raise PdfPreparationError(422, "Unsupported bounded inline WAV")
    return uri


def prepare_audio(body: dict[str, Any]) -> tuple[PreparedAudio, ...]:
    entries = []
    for position, part in audio_parts(body):
        uri = validate_audio_shape(part)
        encoded = uri[len(PREFIX) :]
        try:
            raw = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise PdfPreparationError(422, "Invalid WAV encoding") from exc
        if not 46 <= len(raw) <= MAX_BYTES or base64.b64encode(raw).decode() != encoded:
            raise PdfPreparationError(422, "Invalid bounded canonical WAV encoding")
        header = struct.unpack("<4sI4s4sIHHIIHH4sI", raw[:44])
        if (
            header
            != (
                b"RIFF",
                len(raw) - 8,
                b"WAVE",
                b"fmt ",
                16,
                1,
                1,
                16000,
                32000,
                2,
                16,
                b"data",
                len(raw) - 44,
            )
            or (len(raw) - 44) % 2
        ):
            raise PdfPreparationError(422, "Unsupported finite PCM WAV container")
        entries.append(
            PreparedAudio(
                position, hashlib.sha256(uri.encode()).hexdigest(), len(raw), (len(raw) - 44) // 2
            )
        )
    return tuple(entries)


def validate_prepared_audio(
    body: dict[str, Any], entries: tuple[PreparedAudio, ...], profile: Any
) -> None:
    parts = audio_parts(body)
    if len(parts) != len(entries) or len(parts) > profile.max_audio_files:
        raise ValueError("Audio preparation item mismatch")
    for (position, part), entry in zip(parts, entries, strict=True):
        uri = validate_audio_shape(part)
        if (
            entry.position != position
            or hashlib.sha256(uri.encode()).hexdigest() != entry.digest
            or entry.decoded_bytes > profile.max_audio_bytes
            or entry.frames > profile.max_audio_seconds * 16000
        ):
            raise ValueError("Audio preparation identity or bound mismatch")
    if (
        sum(entry.decoded_bytes for entry in entries) > profile.max_total_audio_bytes
        or sum(entry.frames for entry in entries) > profile.max_total_audio_seconds * 16000
    ):
        raise ValueError("Audio preparation aggregate bound exceeded")
