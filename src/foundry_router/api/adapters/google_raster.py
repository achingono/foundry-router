"""Allow-listed JPEG/WebP containers inspected before constructing native decoders.

These checks bound parser input, metadata, coefficients and raster allocations. Pillow
remains responsible for codec decoding. No media is rendered, rewritten or retained.
"""

from __future__ import annotations

import struct
import time
from array import array
from dataclasses import dataclass

_MAX_DIMENSION = 384
_MAX_SEGMENTS = 32


@dataclass
class ImageWorkBudget:
    """One validation pass across all media in a request, before entropy work."""

    jpeg_pixels: int = 32768
    jpeg_blocks: int = 384

    def consume_jpeg(self, size: tuple[int, int], blocks: int) -> None:
        if max(size) > 128:
            raise ValueError("JPEG dimensions exceed the bounded work profile")
        self.jpeg_pixels -= size[0] * size[1]
        self.jpeg_blocks -= blocks
        if self.jpeg_pixels < 0 or self.jpeg_blocks < 0:
            raise ValueError("JPEG aggregate work bound exceeded")


@dataclass(frozen=True)
class _Huffman:
    # Fixed16-bit prefix table:128KiB/table, <=8 tables/request pass. Building
    # slices is bounded; decoding cost is independent of adversarial code lengths.
    lookup: array[int]


def _dimensions(width: int, height: int, max_pixels: int) -> tuple[int, int]:
    if (
        not 1 <= width <= _MAX_DIMENSION
        or not 1 <= height <= _MAX_DIMENSION
        or width * height > max_pixels
    ):
        raise ValueError("Image dimensions exceed the supported profile")
    return width, height


def preflight_webp(raw: bytes, max_pixels: int) -> tuple[int, int]:
    """Only one static VP8L chunk; no animation or ancillary metadata."""
    if (
        len(raw) < 25
        or raw[:4] != b"RIFF"
        or raw[8:12] != b"WEBP"
        or int.from_bytes(raw[4:8], "little") != len(raw) - 8
    ):
        raise ValueError("Invalid bounded WebP container")
    kind = raw[12:16]
    size = int.from_bytes(raw[16:20], "little")
    if size < 5 or 20 + size + size % 2 != len(raw) or (size % 2 and raw[-1] != 0):
        raise ValueError("Invalid WebP chunk bounds")
    data = memoryview(raw)[20 : 20 + size]
    if kind == b"VP8L":
        bits = int.from_bytes(data[1:5], "little")
        if data[0] != 0x2F or bits >> 29:
            raise ValueError("Unsupported WebP lossless header")
        width = (bits & 0x3FFF) + 1
        height = ((bits >> 14) & 0x3FFF) + 1
    else:
        raise ValueError("Unsupported WebP container chunk")
    return _dimensions(width, height, max_pixels)


def _quantization(data: bytes, tables: set[int]) -> None:
    offset = 0
    while offset < len(data):
        selector = data[offset]
        if selector > 3 or selector in tables or offset + 65 > len(data):
            raise ValueError("Unsupported JPEG quantization table")
        if 0 in data[offset + 1 : offset + 65]:
            raise ValueError("Invalid JPEG quantization values")
        tables.add(selector)
        offset += 65
    if not data:
        raise ValueError("Empty JPEG quantization table")


def _huffman(data: bytes, tables: dict[int, _Huffman]) -> None:
    offset = 0
    while offset < len(data):
        selector = data[offset]
        if (
            selector not in {0, 1, 2, 3, 16, 17, 18, 19}
            or selector in tables
            or offset + 17 > len(data)
        ):
            raise ValueError("Unsupported JPEG Huffman table")
        counts = data[offset + 1 : offset + 17]
        count = sum(counts)
        available = 1
        for value in counts:
            available = available * 2 - value
            if available < 0:
                raise ValueError("Oversubscribed JPEG Huffman table")
        # JPEG disallows an all-ones code and empty/excessive alphabets.
        if not available or not 1 <= count <= 256 or offset + 17 + count > len(data):
            raise ValueError("Invalid JPEG Huffman alphabet")
        symbols = data[offset + 17 : offset + 17 + count]
        if len(set(symbols)) != len(symbols) or any(
            (
                value > 11
                if selector < 16
                else (value & 15) > 10 or (value & 15 == 0 and value not in {0, 240})
            )
            for value in symbols
        ):
            raise ValueError("Unsupported JPEG Huffman symbols")
        lookup = array("H", [0]) * 65536
        code = index = 0
        for length, amount in enumerate(counts, 1):
            for _ in range(amount):
                start = code << (16 - length)
                count_prefixes = 1 << (16 - length)
                lookup[start : start + count_prefixes] = (
                    array("H", [(symbols[index] << 5) | length]) * count_prefixes
                )
                index += 1
                code += 1
            code <<= 1
        tables[selector] = _Huffman(lookup)
        offset += 17 + count
    if not data:
        raise ValueError("Empty JPEG Huffman table")


def _frame(data: bytes, max_pixels: int) -> tuple[tuple[int, int], dict[int, tuple[int, int, int]]]:
    if len(data) != 15 or data[0] != 8 or data[5] != 3:
        raise ValueError("Only three-component baseline JPEG is supported")
    height, width = struct.unpack(">HH", data[1:5])
    components: dict[int, tuple[int, int, int]] = {}
    sampling_sum = 0
    for offset in (6, 9, 12):
        identity, sampling, table = data[offset : offset + 3]
        horizontal, vertical = sampling >> 4, sampling & 15
        if (
            identity in components
            or not 1 <= horizontal <= 4
            or not 1 <= vertical <= 4
            or table > 3
        ):
            raise ValueError("Unsupported JPEG component sampling")
        sampling_sum += horizontal * vertical
        components[identity] = table, horizontal, vertical
    if sampling_sum > 10:
        raise ValueError("JPEG coefficient bound exceeded")
    return _dimensions(width, height, max_pixels), components


def _scan(
    data: bytes,
    components: dict[int, tuple[int, int, int]],
    quant: set[int],
    huffman: dict[int, _Huffman],
) -> list[tuple[int, int, int]]:
    if len(data) != 10 or data[0] != 3 or data[-3:] != b"\x00\x3f\x00":
        raise ValueError("Only complete sequential JPEG scans are supported")
    seen: set[int] = set()
    blocks: list[tuple[int, int, int]] = []
    for offset in (1, 3, 5):
        identity, selector = data[offset : offset + 2]
        dc, ac = selector >> 4, selector & 15
        if (
            identity not in components
            or identity in seen
            or components[identity][0] not in quant
            or dc > 3
            or ac > 3
            or dc not in huffman
            or ac + 16 not in huffman
        ):
            raise ValueError("Unsupported JPEG scan tables")
        seen.add(identity)
        _, horizontal, vertical = components[identity]
        blocks.append((horizontal * vertical, dc, ac + 16))
    return blocks


class _Bits:
    """Finite baseline entropy bit reader; never reads across a marker."""

    def __init__(self, raw: bytes, offset: int) -> None:
        self.raw = raw
        self.offset = offset
        self.buffer = self.count = self.work = 0
        # Each coded coefficient has <=16 code + <=11 value bits; sampling bound
        # yields <=6912 blocks at 384 square. Limit independent of provider data.
        self.max_work = 6912 * 64 * 27

    def take(self, length: int) -> int:
        self.work += length
        if self.work > self.max_work:
            raise ValueError("JPEG entropy work bound exceeded")
        while self.count < length:
            if self.offset >= len(self.raw):
                raise ValueError("Truncated JPEG entropy")
            value = self.raw[self.offset]
            self.offset += 1
            if value == 255:
                if self.offset >= len(self.raw) or self.raw[self.offset] != 0:
                    raise ValueError("JPEG entropy ended before expected blocks")
                self.offset += 1
            self.buffer = (self.buffer << 8) | value
            self.count += 8
        self.count -= length
        value = (self.buffer >> self.count) & ((1 << length) - 1)
        self.buffer &= (1 << self.count) - 1
        return value

    def symbol(self, table: _Huffman) -> int:
        while self.count < 16 and self.offset < len(self.raw):
            value = self.raw[self.offset]
            if value == 255:
                if self.offset + 1 >= len(self.raw) or self.raw[self.offset + 1] != 0:
                    break
                self.offset += 1
            self.offset += 1
            self.buffer = (self.buffer << 8) | value
            self.count += 8
        if self.count >= 16:
            prefix = self.buffer >> (self.count - 16)
        else:
            # Fill only the lookup prefix with1s; do not fabricate entropy bits.
            prefix = (self.buffer << (16 - self.count)) | ((1 << (16 - self.count)) - 1)
        encoded = table.lookup[prefix]
        length = encoded & 31
        if not length or length > self.count:
            raise ValueError("Invalid or truncated JPEG entropy code")
        self.take(length)
        return encoded >> 5

    def marker(self, expected: int) -> None:
        if self.count > 7 or self.buffer != (1 << self.count) - 1:
            raise ValueError("Invalid JPEG entropy padding")
        self.buffer = self.count = 0
        if self.raw[self.offset : self.offset + 2] != bytes((255, expected)):
            raise ValueError("Invalid JPEG entropy marker position")
        self.offset += 2


def _block(bits: _Bits, dc: _Huffman, ac: _Huffman) -> None:
    bits.take(bits.symbol(dc))
    coefficient = 1
    while coefficient < 64:
        symbol = bits.symbol(ac)
        if symbol == 0:
            return
        if symbol == 240:
            coefficient += 16
            if coefficient > 64:
                raise ValueError("JPEG zero run exceeds block")
            continue
        coefficient += symbol >> 4
        if coefficient >= 64:
            raise ValueError("JPEG coefficient run exceeds block")
        bits.take(symbol & 15)
        coefficient += 1


def _entropy(
    raw: bytes,
    offset: int,
    *,
    restart_interval: int,
    size: tuple[int, int],
    components: dict[int, tuple[int, int, int]],
    blocks: list[tuple[int, int, int]],
    huffman: dict[int, _Huffman],
    deadline: float | None,
) -> None:
    horizontal = max(component[1] for component in components.values()) * 8
    vertical = max(component[2] for component in components.values()) * 8
    mcus = ((size[0] + horizontal - 1) // horizontal) * ((size[1] + vertical - 1) // vertical)
    bits = _Bits(raw, offset)
    restart = 0
    for index in range(mcus):
        if deadline is not None and time.monotonic() >= deadline:
            raise ValueError("Request intake deadline exceeded")
        for amount, dc, ac in blocks:
            for _ in range(amount):
                _block(bits, huffman[dc], huffman[ac])
        if restart_interval and (index + 1) % restart_interval == 0 and index + 1 < mcus:
            bits.marker(0xD0 + restart)
            restart = (restart + 1) % 8
    bits.marker(0xD9)
    if bits.offset != len(raw):
        raise ValueError("Trailing JPEG entropy data")


def preflight_jpeg(
    raw: bytes,
    max_pixels: int,
    *,
    deadline: float | None = None,
    work_budget: ImageWorkBudget | None = None,
) -> tuple[int, int]:
    """One baseline frame/scan and bounded tables; no metadata except empty JFIF."""
    if not raw.startswith(b"\xff\xd8"):
        raise ValueError("Invalid JPEG signature")
    offset = 2
    size = None
    components: dict[int, tuple[int, int, int]] = {}
    quant: set[int] = set()
    huffman: dict[int, _Huffman] = {}
    jfif = saw_restart = False
    restart_interval = 0
    for _ in range(_MAX_SEGMENTS):
        if offset + 4 > len(raw) or raw[offset] != 255:
            raise ValueError("Invalid JPEG segment")
        marker = raw[offset + 1]
        length = int.from_bytes(raw[offset + 2 : offset + 4])
        end = offset + 2 + length
        if length < 2 or end > len(raw):
            raise ValueError("Invalid JPEG segment bounds")
        data = raw[offset + 4 : end]
        if marker == 0xE0:
            if (
                jfif
                or offset != 2
                or len(data) != 14
                or data[:5] != b"JFIF\x00"
                or data[5] != 1
                or data[6] > 2
                or data[7] > 2
                or not int.from_bytes(data[8:10])
                or not int.from_bytes(data[10:12])
                or data[-2:] != b"\x00\x00"
            ):
                raise ValueError("Unsupported JPEG metadata")
            jfif = True
        elif marker == 0xDB:
            _quantization(data, quant)
        elif marker == 0xC4:
            _huffman(data, huffman)
        elif marker == 0xDD:
            if saw_restart or len(data) != 2:
                raise ValueError("Invalid JPEG restart interval")
            saw_restart = True
            restart_interval = int.from_bytes(data)
        elif marker == 0xC0 and size is None:
            size, components = _frame(data, max_pixels)
        elif marker == 0xDA and size is not None:
            blocks = _scan(data, components, quant, huffman)
            if work_budget is not None:
                horizontal = max(component[1] for component in components.values()) * 8
                vertical = max(component[2] for component in components.values()) * 8
                mcus = ((size[0] + horizontal - 1) // horizontal) * (
                    (size[1] + vertical - 1) // vertical
                )
                work_budget.consume_jpeg(size, mcus * sum(block[0] for block in blocks))
            _entropy(
                raw,
                end,
                restart_interval=restart_interval,
                size=size,
                components=components,
                blocks=blocks,
                huffman=huffman,
                deadline=deadline,
            )
            return size
        else:
            raise ValueError("Unsupported JPEG segment")
        offset = end
    raise ValueError("JPEG segment count exceeded")
