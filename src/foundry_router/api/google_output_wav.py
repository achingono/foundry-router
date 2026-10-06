"""Finite generated WAV inspection without codecs, conversion or unbounded work."""

from __future__ import annotations

import base64
import binascii
import struct
from dataclasses import dataclass

MAX_OUTPUT_WAV_BYTES = 480044
OUTPUT_SAMPLE_RATE = 24000


@dataclass(frozen=True, repr=False)
class OutputWavFacts:
    decoded_bytes: int
    frames: int


def inspect_output_wav(raw: bytes) -> OutputWavFacts:
    if not 46 <= len(raw) <= MAX_OUTPUT_WAV_BYTES:
        raise ValueError("Generated WAV exceeds finite boundary")
    data_bytes = len(raw) - 44
    header = struct.unpack("<4sI4s4sIHHIIHH4sI", raw[:44])
    if data_bytes % 2 or header != (
        b"RIFF",
        len(raw) - 8,
        b"WAVE",
        b"fmt ",
        16,
        1,
        1,
        24000,
        48000,
        2,
        16,
        b"data",
        data_bytes,
    ):
        raise ValueError("Unsupported generated PCM WAV")
    return OutputWavFacts(len(raw), data_bytes // 2)


def decode_output_wav(encoded: str) -> tuple[bytes, OutputWavFacts]:
    if (
        not isinstance(encoded, str)
        or not encoded
        or len(encoded) > 4 * ((MAX_OUTPUT_WAV_BYTES + 2) // 3)
    ):
        raise ValueError("Generated WAV encoding exceeds boundary")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("Invalid generated WAV encoding") from exc
    facts = inspect_output_wav(raw)
    if base64.b64encode(raw).decode() != encoded:
        raise ValueError("Invalid canonical generated WAV")
    return raw, facts


def output_wav_ready() -> bool:
    raw = (
        struct.pack(
            "<4sI4s4sIHHIIHH4sI",
            b"RIFF",
            38,
            b"WAVE",
            b"fmt ",
            16,
            1,
            1,
            24000,
            48000,
            2,
            16,
            b"data",
            2,
        )
        + b"\0\0"
    )
    return inspect_output_wav(raw).frames == 1
