"""Finite PDF grammar checked before the reviewed dependency sees any bytes.

No rendering, extraction, stream decompression, or caller-directed I/O. This
module imports only stdlib so the worker can impose limits before loading pypdf.
"""

from __future__ import annotations

import io
import logging
import math
import re
from dataclasses import dataclass
from typing import Any

_SPACE = b"\x00\t\n\x0c\r "
_DELIMITERS = _SPACE + b"()<>[]{}/%"
_MAX_BYTES = 65536
_MAX_NODES = 2048
_MAX_DEPTH = 16
_STANDARD_FONTS = {
    "Courier",
    "Courier-Bold",
    "Courier-Oblique",
    "Courier-BoldOblique",
    "Helvetica",
    "Helvetica-Bold",
    "Helvetica-Oblique",
    "Helvetica-BoldOblique",
    "Times-Roman",
    "Times-Bold",
    "Times-Italic",
    "Times-BoldItalic",
    "Symbol",
    "ZapfDingbats",
}


@dataclass(frozen=True)
class Reference:
    number: int
    generation: int


@dataclass(frozen=True)
class Name:
    value: str


@dataclass(frozen=True)
class RawStream:
    dictionary: dict[str, Any]
    data: bytes


class Tokens:
    """Bounded raw PDF tokenizer; no inline-image or codec handling."""

    def __init__(self, data: bytes) -> None:
        self.data = data
        self.position = 0
        self.nodes = 0

    def space(self) -> None:
        while self.position < len(self.data):
            if self.data[self.position] in _SPACE:
                self.position += 1
            elif self.data[self.position] == ord("%"):
                endings = [
                    end
                    for separator in (b"\r", b"\n")
                    if (end := self.data.find(separator, self.position)) >= 0
                ]
                self.position = min(endings) + 1 if endings else len(self.data)
            else:
                break

    def word(self) -> bytes:
        self.space()
        start = self.position
        while self.position < len(self.data) and self.data[self.position] not in _DELIMITERS:
            self.position += 1
        if self.position == start:
            raise ValueError("Invalid PDF token")
        return self.data[start : self.position]

    def value(self, depth: int = 0) -> Any:
        self.nodes += 1
        if depth > _MAX_DEPTH or self.nodes > _MAX_NODES:
            raise ValueError("PDF syntax work limit exceeded")
        self.space()
        if self.position >= len(self.data):
            raise ValueError("Truncated PDF syntax")
        if self.data.startswith(b"<<", self.position):
            self.position += 2
            result: dict[str, Any] = {}
            while True:
                self.space()
                if self.data.startswith(b">>", self.position):
                    self.position += 2
                    return result
                key = self.value(depth + 1)
                if not isinstance(key, Name) or key.value in result:
                    raise ValueError("Invalid or duplicate PDF dictionary key")
                result[key.value] = self.value(depth + 1)
        marker = self.data[self.position]
        if marker == ord("["):
            self.position += 1
            array: list[Any] = []
            while True:
                self.space()
                if self.position < len(self.data) and self.data[self.position] == ord("]"):
                    self.position += 1
                    return array
                if len(array) >= 256:
                    raise ValueError("PDF array exceeds bound")
                array.append(self.value(depth + 1))
        if marker == ord("/"):
            self.position += 1
            start = self.position
            while self.position < len(self.data) and self.data[self.position] not in _DELIMITERS:
                self.position += 1
            raw = self.data[start : self.position]
            if not re.fullmatch(rb"[A-Za-z0-9_.+-]{1,64}", raw):
                raise ValueError("Unsupported PDF name encoding")
            return Name(raw.decode("ascii"))
        if marker == ord("("):
            return self._string()
        if marker == ord("<"):
            self.position += 1
            end = self.data.find(b">", self.position)
            if end < 0:
                raise ValueError("Truncated PDF hexadecimal string")
            raw = re.sub(rb"\s", b"", self.data[self.position : end])
            if not re.fullmatch(rb"[0-9A-Fa-f]*", raw):
                raise ValueError("Invalid PDF hexadecimal string")
            self.position = end + 1
            return bytes.fromhex((raw + (b"0" if len(raw) % 2 else b"")).decode())
        word = self.word()
        if word in (b"true", b"false", b"null"):
            return {b"true": True, b"false": False, b"null": None}[word]
        if not re.fullmatch(rb"[+-]?(?:\d+(?:\.\d*)?|\.\d+)", word):
            raise ValueError("Unsupported PDF object")
        number: int | float = float(word) if b"." in word else int(word)
        if not math.isfinite(number) or abs(number) > 1000000:
            raise ValueError("PDF number exceeds bound")
        saved = self.position
        if isinstance(number, int) and number >= 0:
            match = re.match(
                rb"[\x00\t\n\x0c\r ]+(\d+)[\x00\t\n\x0c\r ]+R(?=$|[\x00\t\n\x0c\r ()<>\[\]{}/%])",
                self.data[saved:],
            )
            if match:
                self.position += match.end()
                return Reference(number, int(match[1]))
        return number

    def _string(self) -> bytes:
        self.position += 1
        result = bytearray()
        nesting = 1
        while self.position < len(self.data):
            char = self.data[self.position]
            self.position += 1
            if char == ord("\\"):
                if self.position >= len(self.data):
                    break
                char = self.data[self.position]
                self.position += 1
                escapes = {ord("n"): 10, ord("r"): 13, ord("t"): 9, ord("b"): 8, ord("f"): 12}
                if char in escapes:
                    result.append(escapes[char])
                elif char in b"01234567":
                    digits = bytearray([char])
                    while (
                        len(digits) < 3
                        and self.position < len(self.data)
                        and self.data[self.position] in b"01234567"
                    ):
                        digits.append(self.data[self.position])
                        self.position += 1
                    result.append(int(digits, 8) % 256)
                elif char == 13:
                    if self.data[self.position : self.position + 1] == b"\n":
                        self.position += 1
                elif char != 10:
                    result.append(char)
            elif char == ord("("):
                nesting += 1
                if nesting > _MAX_DEPTH:
                    raise ValueError("PDF string depth exceeded")
                result.append(char)
            elif char == ord(")"):
                nesting -= 1
                if not nesting:
                    if len(result) > 16384:
                        raise ValueError("PDF string exceeds bound")
                    return bytes(result)
                result.append(char)
            else:
                result.append(char)
        raise ValueError("Truncated PDF string")


def _only(dictionary: Any, keys: set[str]) -> dict[str, Any]:
    if not isinstance(dictionary, dict) or set(dictionary) - keys:
        raise ValueError("Unsupported PDF dictionary")
    return dictionary


def _integer(value: Any, lower: int, upper: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not lower <= value <= upper:
        raise ValueError("Invalid bounded PDF integer")
    return int(value)


def _raw_objects(data: bytes) -> tuple[dict[Reference, Any], dict[str, Any], dict[int, int]]:
    if not 1 <= len(data) <= _MAX_BYTES or not re.match(rb"%PDF-1\.[4-7]\r?\n", data):
        raise ValueError("Unsupported PDF header or byte size")
    ending = re.search(rb"startxref\r?\n(\d+)\r?\n%%EOF\r?\n?\Z", data)
    if ending is None:
        raise ValueError("Invalid PDF terminal framing")
    offset = int(ending[1])
    if not 0 < offset < ending.start() or not data.startswith(b"xref\n", offset):
        raise ValueError("PDF requires exact classic xref offset")
    table = Tokens(data[offset + 5 : ending.start()])
    table.space()
    if table.word() != b"0":
        raise ValueError("PDF xref must start at zero")
    size = _integer(int(table.word()), 2, 257)
    table.space()
    entries: dict[int, int] = {}
    for number in range(size):
        entry = re.match(rb"(\d{10}) (\d{5}) ([nf])(?: \r?\n|\r\n)", table.data[table.position :])
        if entry is None:
            raise ValueError("Invalid PDF xref entry")
        table.position += entry.end()
        position, generation, kind = int(entry[1]), int(entry[2]), entry[3]
        if number == 0:
            if (position, generation, kind) != (0, 65535, b"f"):
                raise ValueError("Invalid PDF free object")
        elif kind != b"n" or generation != 0 or not 0 < position < offset:
            raise ValueError("Unsupported PDF xref generation/free entry")
        else:
            entries[number] = position
    if table.word() != b"trailer":
        raise ValueError("PDF requires one classic trailer")
    trailer = _only(table.value(), {"Size", "Root", "Info"})
    if _integer(trailer.get("Size"), 2, 257) != size:
        raise ValueError("PDF trailer size mismatch")
    table.space()
    if table.position != len(table.data):
        raise ValueError("PDF trailing xref syntax")
    objects: dict[Reference, Any] = {}
    ordered = sorted(entries.items(), key=lambda entry: entry[1])
    if len({position for _, position in ordered}) != len(ordered):
        raise ValueError("Duplicate PDF xref offsets")
    first = ordered[0][1]
    prefix = Tokens(data[:first])
    prefix.space()
    if prefix.position != first:
        raise ValueError("Unindexed PDF prefix")
    total_nodes = 0
    for index, (number, position) in enumerate(ordered):
        end = ordered[index + 1][1] if index + 1 < len(ordered) else offset
        raw = Tokens(data[position:end])
        if raw.word() != str(number).encode() or raw.word() != b"0" or raw.word() != b"obj":
            raise ValueError("PDF object header does not match xref")
        value = raw.value()
        raw.space()
        if isinstance(value, dict) and raw.data.startswith(b"stream", raw.position):
            _only(value, {"Length"})
            length = _integer(value.get("Length"), 0, _MAX_BYTES)
            if not raw.data.startswith(b"stream\n", raw.position):
                raise ValueError("Unsupported PDF stream framing")
            raw.position += 7
            content = raw.data[raw.position : raw.position + length]
            raw.position += length
            if len(content) != length or not raw.data.startswith(b"\nendstream", raw.position):
                raise ValueError("PDF stream length/span mismatch")
            raw.position += 10
            if raw.data[raw.position : raw.position + 1] not in (b"\n", b"\r", b" ", b"\t"):
                raise ValueError("Invalid PDF stream terminator boundary")
            value = RawStream(value, content)
        if raw.word() != b"endobj":
            raise ValueError("Invalid PDF object terminator")
        raw.space()
        if raw.position != len(raw.data):
            raise ValueError("Unindexed PDF object syntax")
        total_nodes += raw.nodes
        if total_nodes > _MAX_NODES:
            raise ValueError("PDF object work exceeds bound")
        objects[Reference(number, 0)] = value
    return objects, trailer, entries


def _content(data: bytes, fonts: set[str], *, remaining_operations: int) -> int:
    tokens = Tokens(data)
    operands: list[Any] = []
    text_open = False
    selected_font = False
    operations = 0
    arities = {
        "BT": 0,
        "ET": 0,
        "Tf": 2,
        "Tj": 1,
        "TJ": 1,
        "Td": 2,
        "TD": 2,
        "Tm": 6,
        "T*": 0,
        "Tc": 1,
        "Tw": 1,
        "Tz": 1,
        "TL": 1,
        "Ts": 1,
        "Tr": 1,
        "g": 1,
        "rg": 3,
        "k": 4,
    }
    while True:
        tokens.space()
        if tokens.position == len(data):
            break
        char = data[tokens.position]
        if char in b"/([<+-.0123456789":
            operands.append(tokens.value())
            if len(operands) > 6:
                raise ValueError("PDF content operand bound exceeded")
            continue
        operator = tokens.word().decode("ascii")
        operations += 1
        if (
            operations > remaining_operations
            or operator not in arities
            or len(operands) != arities[operator]
        ):
            raise ValueError("Unsupported PDF content operator")
        if operator == "BT":
            if text_open:
                raise ValueError("Nested PDF text object")
            text_open = True
            selected_font = False
        elif operator == "ET":
            if not text_open:
                raise ValueError("Unbalanced PDF text object")
            text_open = False
        elif operator not in {"g", "rg", "k"} and not text_open:
            raise ValueError("PDF text operation outside text object")
        if operator == "Tf":
            if not isinstance(operands[0], Name) or operands[0].value not in fonts:
                raise ValueError("Undeclared PDF font")
            _number(operands[1], 0, 1000, positive=True)
            selected_font = True
        elif operator in {"Tj", "TJ"}:
            if not selected_font:
                raise ValueError("PDF text lacks standard font")
            strings = operands if operator == "Tj" else operands[0]
            if not isinstance(strings, list) or (
                operator == "Tj" and not isinstance(strings[0], bytes)
            ):
                raise ValueError("Invalid PDF text operands")
            for value in strings:
                if isinstance(value, bytes):
                    if len(value) > 16384 or any(char > 126 or char < 32 for char in value):
                        raise ValueError("PDF text requires bounded printable standard encoding")
                else:
                    _number(value, -14400, 14400)
        elif operator not in {"BT", "ET", "Tf"}:
            for operand in operands:
                _number(
                    operand,
                    0 if operator in {"g", "rg", "k", "Tr"} else -14400,
                    1
                    if operator in {"g", "rg", "k"}
                    else 7
                    if operator == "Tr"
                    else 1000
                    if operator == "Tz"
                    else 14400,
                    positive=operator == "Tz",
                )
            if operator == "Tr" and not isinstance(operands[0], int):
                raise ValueError("PDF rendering mode must be integer")
        operands = []
    if operands or text_open:
        raise ValueError("Truncated PDF content object")
    return operations


def _number(value: Any, lower: float, upper: float, *, positive: bool = False) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or not lower <= value <= upper
        or (positive and value <= 0)
    ):
        raise ValueError("Invalid bounded PDF number")
    return float(value)


def inspect_pdf(data: bytes) -> int:
    """Return verified page count for the deliberately restricted PDF contract."""
    objects, trailer, entries = _raw_objects(data)
    used: set[Reference] = set()
    resource_cache: dict[Reference, set[str]] = {}
    direct_resource_cache: dict[int, set[str]] = {}
    font_cache: set[Reference] = set()
    content_operations = 0

    def resolve(reference: Any) -> Any:
        if not isinstance(reference, Reference) or reference not in objects or reference in used:
            raise ValueError("Missing, repeated or cyclic PDF reference")
        used.add(reference)
        return objects[reference]

    catalog = _only(resolve(trailer.get("Root")), {"Type", "Pages"})
    if catalog.get("Type") != Name("Catalog"):
        raise ValueError("PDF root must be catalog")

    def resources(value: Any) -> set[str]:
        if isinstance(value, dict) and id(value) in direct_resource_cache:
            return direct_resource_cache[id(value)]
        if isinstance(value, Reference) and value in resource_cache:
            return resource_cache[value]
        dictionary = _only(
            resolve(value) if isinstance(value, Reference) else value, {"Font", "ProcSet"}
        )
        if "ProcSet" in dictionary and dictionary["ProcSet"] != [Name("PDF"), Name("Text")]:
            raise ValueError("Unsupported PDF process set")
        fonts = _only(
            dictionary.get("Font", {}),
            set(dictionary.get("Font", {}))
            if isinstance(dictionary.get("Font", {}), dict)
            else set(),
        )
        if len(fonts) > 14:
            raise ValueError("PDF font count exceeded")
        for reference in fonts.values():
            if isinstance(reference, Reference) and reference in font_cache:
                continue
            font = _only(resolve(reference), {"Type", "Subtype", "BaseFont", "Encoding"})
            if (
                font.get("Type") != Name("Font")
                or font.get("Subtype") != Name("Type1")
                or font.get("BaseFont") not in {Name(name) for name in _STANDARD_FONTS}
                or font.get("Encoding", Name("StandardEncoding")) != Name("StandardEncoding")
            ):
                raise ValueError("PDF requires standard built-in fonts")
            font_cache.add(reference)
        if isinstance(value, Reference):
            resource_cache[value] = set(fonts)
        elif isinstance(value, dict):
            direct_resource_cache[id(value)] = set(fonts)
        return set(fonts)

    def pages(
        reference: Any, parent: Reference | None, inherited: dict[str, Any], depth: int
    ) -> int:
        nonlocal content_operations
        if depth > _MAX_DEPTH:
            raise ValueError("PDF page tree depth exceeded")
        node = _only(
            resolve(reference),
            {"Type", "Parent", "Kids", "Count", "MediaBox", "CropBox", "Resources", "Contents"},
        )
        if node.get("Parent") != parent:
            raise ValueError("PDF page parent mismatch")
        if "Resources" in node:
            resources(node["Resources"])
        for key in ("MediaBox", "CropBox"):
            if key in node:
                box = node[key]
                if not isinstance(box, list) or len(box) != 4:
                    raise ValueError("Invalid declared PDF page geometry")
                coordinates = [_number(value, -14400, 14400) for value in box]
                if (
                    not 0 < coordinates[2] - coordinates[0] <= 14400
                    or not 0 < coordinates[3] - coordinates[1] <= 14400
                ):
                    raise ValueError("PDF declared page dimensions exceeded")
        merged = {
            **inherited,
            **{key: node[key] for key in ("MediaBox", "CropBox", "Resources") if key in node},
        }
        if node.get("Type") == Name("Pages"):
            if "Contents" in node:
                raise ValueError("PDF page-tree contents unsupported")
            children = node.get("Kids")
            if not isinstance(children, list) or not 1 <= len(children) <= 4:
                raise ValueError("PDF page child bound exceeded")
            count = sum(pages(child, reference, merged, depth + 1) for child in children)
            if count != _integer(node.get("Count"), 1, 4) or not 1 <= count <= 4:
                raise ValueError("PDF page count mismatch")
            return count
        if node.get("Type") != Name("Page") or "Kids" in node or "Count" in node:
            raise ValueError("Invalid PDF page node")
        for key in ("MediaBox", "CropBox"):
            box = merged.get(key)
            if box is None and key == "CropBox":
                continue
            if not isinstance(box, list) or len(box) != 4:
                raise ValueError("PDF page requires bounded geometry")
            coordinates = [_number(value, -14400, 14400) for value in box]
            if (
                not 0 < coordinates[2] - coordinates[0] <= 14400
                or not 0 < coordinates[3] - coordinates[1] <= 14400
            ):
                raise ValueError("PDF page dimensions exceeded")
        fonts = resources(merged.get("Resources", {}))
        contents = node.get("Contents", [])
        for content in contents if isinstance(contents, list) else [contents]:
            stream = resolve(content)
            if not isinstance(stream, RawStream):
                raise ValueError("PDF contents must be direct-length raw stream")
            content_operations += _content(
                stream.data, fonts, remaining_operations=_MAX_NODES - content_operations
            )
        return 1

    count = pages(catalog.get("Pages"), None, {}, 0)
    if "Info" in trailer:
        info = _only(
            resolve(trailer["Info"]),
            {
                "Producer",
                "Creator",
                "Title",
                "Author",
                "Subject",
                "Keywords",
                "CreationDate",
                "ModDate",
            },
        )
        if any(not isinstance(value, bytes) or len(value) > 1024 for value in info.values()):
            raise ValueError("Unsupported PDF info values")
    if used != set(objects):
        raise ValueError("Unreachable or unsupported PDF objects")
    # All raw containers/content have passed before dependency construction.
    from pypdf import PdfReader  # noqa: PLC0415 -- load only after raw validation

    class RejectWarning(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            _ = record
            raise ValueError("PDF dependency reported a repair or warning")

    def compare(raw: Any, parsed: Any) -> None:
        from pypdf.generic import (  # noqa: PLC0415 -- dependency only after raw grammar
            ArrayObject,
            BooleanObject,
            ByteStringObject,
            DictionaryObject,
            FloatObject,
            IndirectObject,
            NameObject,
            NullObject,
            NumberObject,
            StreamObject,
            TextStringObject,
        )

        if isinstance(raw, Reference):
            valid = isinstance(parsed, IndirectObject) and (parsed.idnum, parsed.generation) == (
                raw.number,
                raw.generation,
            )
        elif isinstance(raw, Name):
            valid = isinstance(parsed, NameObject) and str(parsed) == "/" + raw.value
        elif isinstance(raw, RawStream):
            valid = (
                isinstance(parsed, StreamObject)
                and parsed._data == raw.data
                and not set(parsed) - {"/Length"}
            )
        elif isinstance(raw, dict):
            valid = isinstance(parsed, DictionaryObject) and set(parsed) == {
                "/" + key for key in raw
            }
            if valid:
                for key, value in raw.items():
                    compare(value, parsed.raw_get("/" + key))
        elif isinstance(raw, list):
            valid = isinstance(parsed, ArrayObject) and len(parsed) == len(raw)
            if valid:
                for value, other in zip(raw, parsed, strict=True):
                    compare(value, other)
        elif isinstance(raw, bytes):
            valid = (
                isinstance(parsed, (ByteStringObject, TextStringObject))
                and parsed.original_bytes == raw
            )
        elif isinstance(raw, bool):
            valid = isinstance(parsed, BooleanObject) and parsed.value == raw
        elif raw is None:
            valid = isinstance(parsed, NullObject)
        else:
            valid = isinstance(parsed, (NumberObject, FloatObject)) and parsed == raw
        if not valid:
            raise ValueError("PDF dependency disagreed with raw object grammar")

    dependency_logger = logging.getLogger("pypdf")
    handler = RejectWarning(level=logging.WARNING)
    dependency_logger.addHandler(handler)
    try:
        reader = PdfReader(io.BytesIO(data), strict=True)
        for reference, raw in objects.items():
            compare(raw, reader.get_object(reference.number))
        if (
            reader.xref.get(0) != entries
            or set(reader.xref) - {0, 65535}
            or reader.xref_objStm
            or reader.xref_index
        ):
            raise ValueError("PDF dependency repaired xref state")
        if len(reader.pages) != count:
            raise ValueError("PDF dependency page count mismatch")
    finally:
        dependency_logger.removeHandler(handler)
    return count
