"""Deterministic classic PDFs, without compressed streams or personal content."""

from __future__ import annotations


def pdf(objects: list[bytes], *, root: int = 1, trailer: bytes = b"") -> bytes:
    data = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, 1):
        offsets.append(len(data))
        data.extend(f"{number} 0 obj\n".encode() + body + b"\nendobj\n")
    start = len(data)
    data.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets:
        data.extend(f"{offset:010d} 00000 n \n".encode())
    data.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root {root} 0 R ".encode() + trailer + b">>\n"
    )
    data.extend(f"startxref\n{start}\n%%EOF\n".encode())
    return bytes(data)


def document(
    pages: int = 1,
    *,
    content: bytes = b"BT /F1 12 Tf (fixture) Tj ET",
    extra: bytes = b"",
    page_extra: bytes = b"",
) -> bytes:
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b""]
    children = []
    for _ in range(pages):
        page_id = len(objects) + 1
        font_id, stream_id = page_id + 1, page_id + 2
        children.append(f"{page_id} 0 R".encode())
        objects.extend(
            [
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 100 100] /Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {stream_id} 0 R ".encode()
                + page_extra
                + b">>",
                b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
                f"<< /Length {len(content)} ".encode()
                + extra
                + b">>\nstream\n"
                + content
                + b"\nendstream",
            ]
        )
    objects[1] = f"<< /Type /Pages /Count {pages} /Kids [".encode() + b" ".join(children) + b"] >>"
    return pdf(objects)
