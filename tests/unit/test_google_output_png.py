"""Generated PNG exact grammar and finite expansion checks."""

import struct
import zlib

import pytest

from foundry_router.api.google_output_png import inspect_output_png


def chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


def png(*, color=6, row_filter=0, extra=b"", truncated=False, dimensions=1024):
    channels = 4 if color == 6 else 3
    raw = bytes([row_filter]) + b"\0" * (channels * dimensions)
    data = zlib.compress(raw * dimensions + extra)
    if truncated:
        data = data[:-1]
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", dimensions, dimensions, 8, color, 0, 0, 0))
        + chunk(b"IDAT", data)
        + chunk(b"IEND", b"")
    )


@pytest.mark.parametrize("color", [2, 6])
@pytest.mark.parametrize("row_filter", [0, 1, 2, 3, 4])
def test_valid_finite_rasters(color, row_filter):
    raw = png(color=color, row_filter=row_filter)
    result = inspect_output_png(raw)
    assert result["expanded_bytes"] == 1024 * (1 + 1024 * (4 if color == 6 else 3))
    assert result["bytes"] == len(raw)


@pytest.mark.parametrize(
    "raw",
    [
        png(row_filter=5),
        png(extra=b"\0"),
        png(truncated=True),
        png(dimensions=1023),
        png() + b"extra",
        b"\x89PNG\r\n\x1a\n",
        png()[:-12] + chunk(b"tEXt", b"marker") + chunk(b"IEND", b""),
    ],
)
def test_invalid_expansion_dimensions_metadata_and_truncation(raw):
    with pytest.raises(ValueError):
        inspect_output_png(raw)


def test_many_chunks_crc_and_split_idat():
    raw = png()
    compressed = raw[41:-16]
    # Parse exact IDAT payload from the generated fixture.
    length = int.from_bytes(raw[33:37], "big")
    compressed = raw[41 : 41 + length]
    split = (
        raw[:33]
        + chunk(b"IDAT", compressed[:2])
        + chunk(b"IDAT", compressed[2:])
        + chunk(b"IEND", b"")
    )
    assert inspect_output_png(split)["height"] == 1024
    with pytest.raises(ValueError):
        inspect_output_png(
            raw[:33]
            + b"".join(chunk(b"IDAT", bytes([b])) for b in compressed)
            + chunk(b"IEND", b"")
        )
    damaged = bytearray(raw)
    damaged[-1] ^= 1
    with pytest.raises(ValueError):
        inspect_output_png(bytes(damaged))


def test_concatenated_stream_and_duplicate_header_reject():
    raw = png()
    length = int.from_bytes(raw[33:37], "big")
    data = raw[41 : 41 + length]
    for altered in (
        raw[:33] + chunk(b"IDAT", data + zlib.compress(b"extra")) + chunk(b"IEND", b""),
        raw[:33] + raw[8:33] + raw[33:],
    ):
        with pytest.raises(ValueError):
            inspect_output_png(altered)


def test_split_zlib_header_and_bad_deflate_adler():
    raw = png()
    length = int.from_bytes(raw[33:37], "big")
    data = raw[41 : 41 + length]
    split = raw[:33] + chunk(b"IDAT", data[:1]) + chunk(b"IDAT", data[1:]) + chunk(b"IEND", b"")
    assert inspect_output_png(split)["height"] == 1024
    for offset in (2, len(data) - 1):
        damaged = bytearray(data)
        damaged[offset] ^= 255
        with pytest.raises(ValueError):
            inspect_output_png(raw[:33] + chunk(b"IDAT", bytes(damaged)) + chunk(b"IEND", b""))
