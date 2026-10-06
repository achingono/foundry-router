"""Finite raw BGR DIB AVI inspection; no codec execution or media transformation."""

from __future__ import annotations

import base64
import binascii
import hashlib
import re
import struct
from dataclasses import dataclass
from typing import Any

from foundry_router.api.google_pdf import PdfPreparationError

PREFIX = "data:video/avi;base64,"
MAX_BYTES = 65536


@dataclass(frozen=True, repr=False)
class PreparedVideo:
    position: tuple[int, int]
    digest: str
    decoded_bytes: int
    frames: int
    width: int
    height: int


def video_parts(body: dict[str, Any]) -> list[tuple[tuple[int, int], dict[str, Any]]]:
    result: list[tuple[tuple[int, int], dict[str, Any]]] = []
    history = body.get("input")
    if not isinstance(history, list):
        return result
    if len(history) > 256:
        raise PdfPreparationError(422, "Video history bound exceeded")
    for index, item in enumerate(history):
        if not isinstance(item, dict) or not isinstance(item.get("content"), list):
            continue
        if len(item["content"]) > 64:
            raise PdfPreparationError(422, "Video content bound exceeded")
        for part_index, part in enumerate(item["content"]):
            if (
                isinstance(part, dict)
                and part.get("type") == "input_file"
                and isinstance(part.get("file_data"), str)
                and part["file_data"].startswith(PREFIX)
            ):
                if item.get("role") != "user" or len(result) >= 2:
                    raise PdfPreparationError(422, "Unsupported video placement or count")
                result.append(((index, part_index), part))
    return result


def validate_video_shape(part: dict[str, Any]) -> str:
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
                or re.fullmatch(r"[A-Za-z0-9_.-]{1,60}\.avi", part["filename"]) is None
            )
        )
    ):
        raise PdfPreparationError(422, "Unsupported bounded inline AVI")
    return uri


def _chunk(raw: bytes, offset: int, end: int, kind: bytes) -> tuple[bytes, int]:
    if offset + 8 > end or raw[offset : offset + 4] != kind:
        raise ValueError("Invalid AVI chunk ordering")
    size = int.from_bytes(raw[offset + 4 : offset + 8], "little")
    next_offset = offset + 8 + size
    if size % 2 or next_offset > end:
        raise ValueError("Invalid AVI chunk boundary")
    return raw[offset + 8 : next_offset], next_offset


def inspect_video(raw: bytes) -> tuple[int, int, int]:
    if (
        not 236 <= len(raw) <= MAX_BYTES
        or raw[:12] != b"RIFF" + struct.pack("<I", len(raw) - 8) + b"AVI "
    ):
        raise ValueError("Invalid AVI RIFF boundary")
    hdrl, offset = _chunk(raw, 12, len(raw), b"LIST")
    if hdrl[:4] != b"hdrl":
        raise ValueError("Invalid AVI header list")
    avih, hpos = _chunk(hdrl, 4, len(hdrl), b"avih")
    strl, hpos = _chunk(hdrl, hpos, len(hdrl), b"LIST")
    if hpos != len(hdrl) or strl[:4] != b"strl" or len(avih) != 56:
        raise ValueError("Invalid AVI header structure")
    strh, spos = _chunk(strl, 4, len(strl), b"strh")
    strf, spos = _chunk(strl, spos, len(strl), b"strf")
    if spos != len(strl) or len(strh) != 56 or len(strf) != 40:
        raise ValueError("Invalid AVI stream structure")
    header = struct.unpack("<14I", avih)
    frames, width, height = header[4], header[8], header[9]
    if not 1 <= frames <= 4 or not 1 <= width <= 64 or not 1 <= height <= 64:
        raise ValueError("AVI frame or dimension bound exceeded")
    stride = ((width * 3 + 3) // 4) * 4
    frame_bytes = stride * height
    if header != (1000000, frame_bytes, 0, 0, frames, 0, 1, frame_bytes, width, height, 0, 0, 0, 0):
        raise ValueError("Unsupported AVI timing or header")
    expected_stream = struct.pack(
        "<4s4sIHH8I4h",
        b"vids",
        b"DIB ",
        0,
        0,
        0,
        0,
        1,
        1,
        0,
        frames,
        frame_bytes,
        0xFFFFFFFF,
        0,
        0,
        0,
        width,
        height,
    )
    expected_format = struct.pack(
        "<IiiHHIIiiII", 40, width, height, 1, 24, 0, frame_bytes, 0, 0, 0, 0
    )
    if strh != expected_stream or strf != expected_format:
        raise ValueError("Unsupported raw AVI stream format")
    movi, offset = _chunk(raw, offset, len(raw), b"LIST")
    if offset != len(raw) or movi[:4] != b"movi":
        raise ValueError("Invalid AVI movie list")
    mpos = 4
    for _ in range(frames):
        frame, mpos = _chunk(movi, mpos, len(movi), b"00db")
        if len(frame) != frame_bytes:
            raise ValueError("Invalid AVI raw frame length")
        for row in range(height):
            if any(frame[row * stride + width * 3 : (row + 1) * stride]):
                raise ValueError("Noncanonical AVI row padding")
    if mpos != len(movi):
        raise ValueError("AVI frame count mismatch")
    return frames, width, height


def prepare_video(body: dict[str, Any]) -> tuple[PreparedVideo, ...]:
    entries = []
    for position, part in video_parts(body):
        uri = validate_video_shape(part)
        encoded = uri[len(PREFIX) :]
        try:
            raw = base64.b64decode(encoded, validate=True)
            if len(raw) > MAX_BYTES or base64.b64encode(raw).decode() != encoded:
                raise ValueError("Invalid canonical AVI encoding")  # noqa: TRY301
            frames, width, height = inspect_video(raw)
        except (ValueError, binascii.Error) as exc:
            raise PdfPreparationError(422, "Invalid finite raw AVI input") from exc
        entries.append(
            PreparedVideo(
                position, hashlib.sha256(uri.encode()).hexdigest(), len(raw), frames, width, height
            )
        )
    return tuple(entries)


def validate_prepared_video(
    body: dict[str, Any], entries: tuple[PreparedVideo, ...], profile: Any
) -> None:
    parts = video_parts(body)
    if len(parts) != len(entries) or len(parts) > profile.max_video_files:
        raise ValueError("Video preparation item mismatch")
    for (position, part), entry in zip(parts, entries, strict=True):
        uri = validate_video_shape(part)
        if (
            entry.position != position
            or hashlib.sha256(uri.encode()).hexdigest() != entry.digest
            or entry.decoded_bytes > profile.max_video_bytes
            or entry.frames > profile.max_video_frames
            or entry.width * entry.height > profile.max_video_pixels
        ):
            raise ValueError("Video preparation identity or bound mismatch")
    if (
        sum(entry.decoded_bytes for entry in entries) > profile.max_total_video_bytes
        or sum(entry.frames for entry in entries) > profile.max_total_video_frames
    ):
        raise ValueError("Video preparation aggregate bound exceeded")
