"""Bounded small inline images. No paths, URLs, files, rendering or transcoding."""

from __future__ import annotations

import base64
import binascii
import io
import struct
import zlib
from typing import TYPE_CHECKING, Any

from PIL import Image

from foundry_router.api.adapters.google_raster import (
    ImageWorkBudget,
    preflight_jpeg,
    preflight_webp,
)

if TYPE_CHECKING:
    from foundry_router.config.google_features import GoogleFeatureProfile

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_MAX_DIMENSION = 384
_HEADER_BYTES = 13


def validate_inline_image(
    part: dict[str, Any],
    profile: GoogleFeatureProfile,
    *,
    deadline: float | None = None,
    work_budget: ImageWorkBudget | None = None,
) -> int:
    """Return validated decoded bytes; retain no decoded media after this call."""
    if set(part) - {"type", "image_url", "detail"} or part.get("detail", "auto") != "auto":
        raise ValueError("Inline images support only auto detail and image_url")
    uri = part.get("image_url")
    if not isinstance(uri, str):
        raise ValueError("Only enabled inline image data URIs are supported")
    image_format = next(
        (kind for kind in profile.image_formats if uri.startswith(f"data:image/{kind};base64,")),
        None,
    )
    if image_format is None:
        raise ValueError("Only enabled inline image data URIs are supported")
    prefix = f"data:image/{image_format};base64,"
    encoded = uri[len(prefix) :]
    if not encoded or len(encoded) > 4 * ((profile.max_image_bytes + 2) // 3):
        raise ValueError("Inline image exceeds its encoded bound")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("Invalid inline image encoding") from exc
    if len(raw) > profile.max_image_bytes:
        raise ValueError("Inline image exceeds its decoded bound")
    expected_size = None
    if image_format == "png":
        _preflight_png(raw, profile.max_image_pixels)
    elif image_format == "jpeg":
        expected_size = preflight_jpeg(
            raw,
            profile.max_image_pixels,
            deadline=deadline,
            work_budget=work_budget or ImageWorkBudget(jpeg_pixels=profile.max_jpeg_total_pixels),
        )
    else:
        expected_size = preflight_webp(raw, profile.max_image_pixels)
    try:
        with Image.open(io.BytesIO(raw), formats=[image_format.upper()]) as image:
            # Decode only after container, metadata, dimensions and CRC bounds pass.
            _check_raster(image, expected_size)
            image.load()
    except (OSError, ValueError, SyntaxError) as exc:
        raise ValueError("Invalid bounded image raster") from exc
    return len(raw)


def _check_raster(image: Image.Image, expected_size: tuple[int, int] | None) -> None:
    if (
        image.mode not in {"RGB", "RGBA"}
        or (expected_size is not None and image.size != expected_size)
        or getattr(image, "n_frames", 1) != 1
    ):
        raise ValueError("Unsupported bounded image raster")


def _preflight_png(raw: bytes, max_pixels: int) -> None:
    if not raw.startswith(_PNG_SIGNATURE):
        raise ValueError("Image MIME and actual format do not match")
    offset = len(_PNG_SIGNATURE)
    saw_header = False
    saw_data = False
    ended_data = False
    width = height = 0
    channels = 0
    idat_parts: list[bytes] = []
    while offset + 12 <= len(raw):
        size = int.from_bytes(raw[offset : offset + 4])
        kind = raw[offset + 4 : offset + 8]
        end = offset + 12 + size
        if end > len(raw):
            raise ValueError("Truncated PNG container")
        data = raw[offset + 8 : offset + 8 + size]
        crc = int.from_bytes(raw[offset + 8 + size : end])
        if zlib.crc32(kind + data) != crc:
            raise ValueError("Invalid PNG checksum")
        if kind == b"IHDR":
            if saw_header or offset != len(_PNG_SIGNATURE) or size != _HEADER_BYTES:
                raise ValueError("Invalid PNG header")
            width, height, bits, color, compression, filtering, interlace = struct.unpack(
                ">IIBBBBB", data
            )
            if (
                not 1 <= width <= _MAX_DIMENSION
                or not 1 <= height <= _MAX_DIMENSION
                or width * height > max_pixels
                or bits != 8
                or color not in (2, 6)
                or compression != 0
                or filtering != 0
                or interlace != 0
            ):
                raise ValueError("PNG dimensions or encoding exceed the supported profile")
            channels = 3 if color == 2 else 4
            saw_header = True
        elif kind == b"IDAT":
            if not saw_header or ended_data or not size:
                raise ValueError("Invalid PNG data ordering")
            saw_data = True
            idat_parts.append(data)
        elif kind == b"IEND":
            ended_data = True
            if not saw_data or size != 0 or end != len(raw):
                raise ValueError("Invalid PNG ending")
            _check_png_raster_complete(b"".join(idat_parts), width, height, channels)
            return
        else:
            # Reject compressed ancillary metadata, animation and unfamiliar chunks.
            raise ValueError("Unsupported PNG container chunk")
        offset = end
    raise ValueError("Incomplete PNG container")


def _check_png_raster_complete(compressed: bytes, width: int, height: int, channels: int) -> None:
    """Require exact zlib completion and exact scanline expansion.

    Pillow tolerates truncated Adler footers and surplus raster bytes, so
    container/CRC checks alone cannot establish raster integrity. Decompress
    the concatenated IDAT stream with a one-byte surplus allowance: truncated
    streams fail with missing EOF, and surplus compressed or expanded data is
    rejected before the native decoder runs.
    """
    if not compressed:
        raise ValueError("Incomplete PNG raster")
    row_size = 1 + width * channels
    expected = row_size * height
    decompressor = zlib.decompressobj()
    try:
        # One-byte surplus allowance detects over-expansion without unbounded inflate.
        inflated = decompressor.decompress(compressed, expected + 1)
        # Drain any remaining output without expanding beyond the bound.
        if not decompressor.eof:
            inflated += decompressor.decompress(b"", expected + 1 - len(inflated))
    except zlib.error as exc:
        raise ValueError("Invalid PNG compressed stream") from exc
    if (
        len(inflated) != expected
        or not decompressor.eof
        or decompressor.unused_data
        or decompressor.unconsumed_tail
    ):
        raise ValueError("Incomplete PNG raster")
    for row_start in range(0, expected, row_size):
        if inflated[row_start] > 4:
            raise ValueError("Invalid PNG row filter")
