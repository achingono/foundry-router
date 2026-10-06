"""Deterministic harmless adversarial image fixture for tests and local measurements."""


def jpeg_segment(marker: int, data: bytes) -> bytes:
    return b"\xff" + bytes([marker]) + (len(data) + 2).to_bytes(2, "big") + data


def worst_entropy_jpeg(dimension: int = 88, *, all_tables: bool = False) -> bytes:
    # Complete bounded baseline: no subsampling; custom longest allowed16-bit
    # codes, every block includes63 nonzero10-bit AC values. Finite worst work.
    tables = jpeg_segment(0xDB, bytes([0]) + b"\x01" * 64)
    if all_tables:
        tables += jpeg_segment(0xDB, b"".join(bytes([i]) + b"\x01" * 64 for i in (1, 2, 3)))
    counts = bytes(15) + b"\x01"
    tables += jpeg_segment(0xC4, b"\x00" + counts + b"\x0b" + b"\x10" + counts + b"\x0a")
    if all_tables:
        tables += jpeg_segment(
            0xC4,
            b"".join(
                bytes([i]) + counts + bytes([11 if i in (1, 2, 3) else 10])
                for i in (1, 2, 3, 17, 18, 19)
            ),
        )
    frame = jpeg_segment(
        0xC0,
        b"\x08" + dimension.to_bytes(2, "big") * 2 + b"\x03\x01\x11\x00\x02\x11\x00\x03\x11\x00",
    )
    scan = jpeg_segment(0xDA, b"\x03\x01\x00\x02\x00\x03\x00\x00\x3f\x00")
    block = "0" * 16 + "1" * 11 + ("0" * 16 + "1" * 10) * 63
    bits = block * (((dimension + 7) // 8) ** 2 * 3)
    bits += "1" * (-len(bits) % 8)
    entropy = int(bits, 2).to_bytes(len(bits) // 8, "big").replace(b"\xff", b"\xff\x00")
    return b"\xff\xd8" + tables + frame + scan + entropy + b"\xff\xd9"
