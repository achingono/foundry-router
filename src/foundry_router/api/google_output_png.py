"""Finite generated PNG syntax/expansion inspection, intended for isolated workers."""

from __future__ import annotations

import struct
import zlib

MAX_PNG_BYTES = 1048576
DIMENSION = 1024
_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_MAX_CHUNKS = 64


def inspect_output_png(raw: bytes) -> dict[str, int]:
    if not 57 <= len(raw) <= MAX_PNG_BYTES or not raw.startswith(_SIGNATURE):
        raise ValueError("Invalid generated PNG boundary")
    position = len(_SIGNATURE)
    count = 0
    row_size = 0
    rows = 0
    row_position = 0
    inflated = 0
    idat_bytes = 0
    decompressor = None
    zlib_header = bytearray()
    ended = False
    while position + 12 <= len(raw):
        count += 1
        if count > _MAX_CHUNKS:
            raise ValueError("Generated PNG chunk bound exceeded")
        size = int.from_bytes(raw[position : position + 4], "big")
        kind = raw[position + 4 : position + 8]
        end = position + 12 + size
        if end > len(raw):
            raise ValueError("Truncated generated PNG")
        data = raw[position + 8 : position + 8 + size]
        crc = int.from_bytes(raw[position + 8 + size : end], "big")
        if zlib.crc32(kind + data) != crc:
            raise ValueError("Invalid generated PNG checksum")
        if kind == b"IHDR":
            if position != 8 or size != 13:
                raise ValueError("Invalid generated PNG header ordering")
            width, height, bits, color, compression, filtering, interlace = struct.unpack(
                ">IIBBBBB", data
            )
            if (
                width != DIMENSION
                or height != DIMENSION
                or bits != 8
                or color not in (2, 6)
                or compression
                or filtering
                or interlace
            ):
                raise ValueError("Unsupported generated PNG raster")
            row_size = 1 + width * (3 if color == 2 else 4)
        elif kind == b"IDAT":
            if not row_size or ended or count == _MAX_CHUNKS or not size:
                raise ValueError("Invalid generated PNG data ordering")
            idat_bytes += size
            if idat_bytes > MAX_PNG_BYTES:
                raise ValueError("Generated PNG compressed bound exceeded")
            if decompressor is None:
                needed = 2 - len(zlib_header)
                zlib_header.extend(data[:needed])
                remainder = data[needed:]
                if len(zlib_header) < 2:
                    position = end
                    continue
                if (
                    zlib_header[0] & 15 != 8
                    or zlib_header[0] >> 4 > 7
                    or (zlib_header[0] * 256 + zlib_header[1]) % 31
                    or zlib_header[1] & 32
                ):
                    raise ValueError("Unsupported generated PNG zlib header")
                decompressor = zlib.decompressobj()
                data = bytes(zlib_header) + remainder
            pending = data
            while pending:
                remaining = row_size * DIMENSION - inflated
                try:
                    piece = decompressor.decompress(pending, min(row_size, remaining + 1))
                except zlib.error as exc:
                    raise ValueError("Invalid generated PNG compressed stream") from exc
                pending = decompressor.unconsumed_tail
                if len(piece) > remaining:
                    raise ValueError("Generated PNG expansion bound exceeded")
                inflated += len(piece)
                filter_start = 0 if row_position == 0 else row_size - row_position
                if any(piece[index] > 4 for index in range(filter_start, len(piece), row_size)):
                    raise ValueError("Invalid generated PNG row filter")
                completed, row_position = divmod(row_position + len(piece), row_size)
                rows += completed
                if decompressor.unused_data or (decompressor.eof and pending):
                    raise ValueError("Trailing generated PNG compressed data")
        elif kind == b"IEND":
            ended = True
            if (
                size
                or end != len(raw)
                or decompressor is None
                or not decompressor.eof
                or decompressor.unconsumed_tail
                or decompressor.unused_data
                or rows != DIMENSION
                or row_position
                or inflated != row_size * DIMENSION
            ):
                raise ValueError("Incomplete generated PNG raster")
            return {
                "bytes": len(raw),
                "width": DIMENSION,
                "height": DIMENSION,
                "expanded_bytes": inflated,
            }
        else:
            raise ValueError("Unsupported generated PNG chunk")
        position = end
    raise ValueError("Incomplete generated PNG container")
