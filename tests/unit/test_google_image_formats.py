"""Format opt-in, bounded preflight and actual raster/client mapping gates."""

from __future__ import annotations

import base64
import io
import struct

import pytest
from PIL import Image
from pydantic import ValidationError

from foundry_router.api.adapters.google_ai_studio import GoogleAiStudioAdapter
from foundry_router.api.adapters.google_media import validate_inline_image
from foundry_router.api.adapters.google_raster import preflight_jpeg, preflight_webp
from foundry_router.config.google_features import GoogleFeatureProfile
from scripts.quality.google_media_fixtures import worst_entropy_jpeg


def image_bytes(kind, *, width=32, height=32, **options):
    if kind == "webp":
        options.setdefault("lossless", True)
    output = io.BytesIO()
    Image.new("RGB", (width, height), (20, 50, 100)).save(output, format=kind, **options)
    return output.getvalue()


def part(kind, raw):
    return {
        "type": "input_image",
        "image_url": f"data:image/{kind};base64," + base64.b64encode(raw).decode(),
    }


def profile(*formats, **options):
    return GoogleFeatureProfile(
        features=("inline_images",),
        image_formats=formats or ("png",),
        image_input_tokens=258,
        image_token_pricing=True,
        **options,
    )


@pytest.mark.parametrize(
    "kind,options", [("jpeg", {}), ("webp", {"lossless": True}), ("webp", {"lossless": True})]
)
def test_explicit_format_opt_in_and_matching_raster(kind, options):
    raw = image_bytes(kind, **options)
    with pytest.raises(ValueError, match="enabled"):
        validate_inline_image(part(kind, raw), profile())
    assert validate_inline_image(part(kind, raw), profile(kind)) == len(raw)
    with pytest.raises(ValueError):
        validate_inline_image(part("png", raw), profile())
    with pytest.raises(ValueError):
        validate_inline_image(part(kind, raw), profile(kind, max_image_pixels=100))


@pytest.mark.parametrize("formats", [(), ("jpeg", "jpeg"), ("gif",)])
def test_invalid_format_profiles(formats):
    with pytest.raises(ValidationError):
        GoogleFeatureProfile(image_formats=formats)


@pytest.mark.parametrize("kind", ["jpeg", "webp"])
def test_dimension_bombs_rejected_before_decoder(kind, monkeypatch):
    raw = image_bytes(kind, width=385, height=1)
    monkeypatch.setattr(
        Image, "open", lambda *_args, **_kwargs: pytest.fail("native decoder opened")
    )
    with pytest.raises(ValueError, match="dimensions"):
        validate_inline_image(part(kind, raw), profile(kind))


def jpeg_segment(marker, data):
    return b"\xff" + bytes([marker]) + (len(data) + 2).to_bytes(2, "big") + data


def replace_jpeg_segment(raw, marker, transform):
    offset = raw.index(b"\xff" + bytes([marker]))
    size = int.from_bytes(raw[offset + 2 : offset + 4], "big")
    end = offset + size + 2
    return raw[:offset] + jpeg_segment(marker, transform(raw[offset + 4 : end])) + raw[end:]


@pytest.mark.parametrize(
    "transform",
    [
        lambda raw: raw[:-1],
        lambda raw: raw + b"trailer",
        lambda raw: raw[:2] + jpeg_segment(0xE1, b"Exif\x00\x00") + raw[2:],
        lambda raw: replace_jpeg_segment(raw, 0xE0, lambda data: data + b"thumbnail"),
        lambda raw: replace_jpeg_segment(raw, 0xDB, lambda data: bytes([0x10]) + data[1:]),
        lambda raw: replace_jpeg_segment(raw, 0xDB, lambda data: data[:1] + bytes(len(data) - 1)),
        lambda raw: replace_jpeg_segment(
            raw, 0xC4, lambda data: data[:1] + b"\xff" * 16 + data[17:]
        ),
        lambda raw: replace_jpeg_segment(raw, 0xC0, lambda data: data[:7] + b"\x44" + data[8:]),
        lambda raw: replace_jpeg_segment(raw, 0xC0, lambda data: data[:9] + data[6:7] + data[10:]),
        lambda raw: replace_jpeg_segment(raw, 0xDA, lambda data: data[:-1] + b"\x01"),
        lambda raw: replace_jpeg_segment(raw, 0xDA, lambda data: data[:2] + b"\x44" + data[3:]),
        lambda raw: raw.replace(b"\xff\xc0", b"\xff\xc2", 1),
    ],
)
def test_jpeg_malformed_metadata_sampling_tables_scan_fail_preflight(transform, monkeypatch):
    raw = transform(image_bytes("jpeg"))
    monkeypatch.setattr(
        Image, "open", lambda *_args, **_kwargs: pytest.fail("native decoder opened")
    )
    with pytest.raises(ValueError):
        validate_inline_image(part("jpeg", raw), profile("jpeg"))


def test_jpeg_progressive_grayscale_duplicate_tables_and_bounds():
    for raw in [image_bytes("jpeg", progressive=True), b"\xff\xd8\xff\xdb\xff\xff", b"bad"]:
        with pytest.raises(ValueError):
            preflight_jpeg(raw, 147456)
    out = io.BytesIO()
    Image.new("L", (8, 8)).save(out, format="JPEG")
    with pytest.raises(ValueError):
        preflight_jpeg(out.getvalue(), 147456)
    raw = image_bytes("jpeg")
    with pytest.raises(ValueError):
        preflight_jpeg(replace_jpeg_segment(raw, 0xDB, lambda data: data * 2), 147456)
    assert preflight_jpeg(image_bytes("jpeg", width=384, height=384), 147456) == (384, 384)


def test_jpeg_terminal_eoi_cannot_hide_missing_entropy_and_deadline():
    raw = image_bytes("jpeg", width=384, height=384)
    for removed in (1, 100, 1000):
        with pytest.raises(ValueError, match="entropy"):
            preflight_jpeg(raw[: -removed - 2] + b"\xff\xd9", 147456)
    with pytest.raises(ValueError, match="deadline"):
        preflight_jpeg(raw, 147456, deadline=0)


def test_jpeg_work_budget_across_history_before_entropy():
    image = part("jpeg", image_bytes("jpeg", width=128, height=128))
    p = profile("jpeg", max_images=8)
    adapter = GoogleAiStudioAdapter(profile=p)
    body = {
        "input": [{"role": "user", "content": [image, image]}, {"role": "user", "content": [image]}]
    }
    assert adapter.check_request("responses", body) is not None
    with pytest.raises(ValueError, match="dimensions"):
        validate_inline_image(part("jpeg", image_bytes("jpeg", width=129)), p)
    assert validate_inline_image(image, p) > 0


def test_worst_permitted_entropy_layout_complete_and_native_decode():
    raw = worst_entropy_jpeg()
    assert preflight_jpeg(raw, 147456) == (88, 88)
    assert validate_inline_image(part("jpeg", raw), profile("jpeg")) == len(raw)


@pytest.mark.parametrize("option", [{"restart_marker_blocks": 1}, {"restart_marker_rows": 1}])
def test_jpeg_restart_positions_sequence_and_padding(option):
    raw = image_bytes("jpeg", width=128, height=128, **option)
    assert validate_inline_image(part("jpeg", raw), profile("jpeg")) == len(raw)
    marker = raw.index(b"\xff\xd0")
    for modified in (
        raw[:marker] + b"\xff\xd1" + raw[marker + 2 :],
        raw[:marker] + raw[marker + 2 :],
        raw[:marker] + b"\x00" + raw[marker:],
        raw[:-2] + b"\xff\xd0\xff\xd9",
    ):
        with pytest.raises(ValueError):
            preflight_jpeg(modified, 147456)


def minimal_entropy_jpeg(symbol, entropy):
    tables = jpeg_segment(0xDB, b"\x00" + b"\x01" * 64)
    counts = b"\x01" + bytes(15)
    tables += jpeg_segment(0xC4, b"\x00" + counts + b"\x00" + b"\x10" + counts + bytes([symbol]))
    frame = jpeg_segment(0xC0, b"\x08\x00\x01\x00\x01\x03\x01\x11\x00\x02\x11\x00\x03\x11\x00")
    scan = jpeg_segment(0xDA, b"\x03\x01\x00\x02\x00\x03\x00\x00\x3f\x00")
    return b"\xff\xd8" + tables + frame + scan + entropy + b"\xff\xd9"


def test_jpeg_short_codes_final_padding_zrl_and_ac_overflow():
    # Three blocks, each DC0/EOB0:6 bits then two1 padding bits.
    assert preflight_jpeg(minimal_entropy_jpeg(0, b"\x03"), 147456) == (1, 1)
    for raw in (
        minimal_entropy_jpeg(0, b"\x00"),  # bad padding
        minimal_entropy_jpeg(0, b"\x03\x00"),  # unused full byte
        minimal_entropy_jpeg(0, b"\x1f"),  # missing third block
        minimal_entropy_jpeg(240, b"\x00\x00"),  # fourth ZRL crosses coefficient64
        minimal_entropy_jpeg(0xF1, bytes(20)),  # fourth run crosses coefficient64
    ):
        with pytest.raises(ValueError):
            preflight_jpeg(raw, 147456)


def test_lossy_webp_disabled_and_lossless_truncation_rejected():
    with pytest.raises(ValueError, match="chunk"):
        validate_inline_image(part("webp", image_bytes("webp", lossless=False)), profile("webp"))
    raw = image_bytes("webp", lossless=True, width=384, height=384)
    for removed in (2, 10):
        modified = raw[:-removed]
        modified = (
            modified[:4]
            + (len(modified) - 8).to_bytes(4, "little")
            + modified[8:16]
            + (len(modified) - 20).to_bytes(4, "little")
            + modified[20:]
        )
        with pytest.raises(ValueError):
            validate_inline_image(part("webp", modified), profile("webp"))


def webp_chunk(kind, data):
    content = (
        b"WEBP" + kind + struct.pack("<I", len(data)) + data + (b"\x00" if len(data) % 2 else b"")
    )
    return b"RIFF" + struct.pack("<I", len(content)) + content


@pytest.mark.parametrize(
    "raw",
    [
        b"bad",
        webp_chunk(b"VP8X", bytes(10)),
        webp_chunk(b"ANIM", bytes(10)),
        webp_chunk(b"VP8L", b"\x2f" + (1 << 29).to_bytes(4, "little")),
        webp_chunk(b"VP8L", b"\x2f" + (384).to_bytes(4, "little")),
        webp_chunk(b"VP8 ", b"\x11\x00\x00\x9d\x01\x2a\x01\x00\x01\x00"),
        webp_chunk(b"VP8 ", b"\x10\x00\x00\x9d\x01\x2a\x01\x40\x01\x00"),
        webp_chunk(b"VP8 ", b"\xf0\xff\xff\x9d\x01\x2a\x01\x00\x01\x00"),
    ],
)
def test_webp_bad_chunks_versions_scaling_and_dimensions(raw, monkeypatch):
    monkeypatch.setattr(
        Image, "open", lambda *_args, **_kwargs: pytest.fail("native decoder opened")
    )
    with pytest.raises(ValueError):
        validate_inline_image(part("webp", raw), profile("webp"))


def test_webp_no_trailing_metadata_bad_padding_or_truncated_codec():
    raw = image_bytes("webp")
    for modified in [raw + b"trailer", raw[:-1], raw[:12] + b"EXIF" + raw[16:]]:
        with pytest.raises(ValueError):
            preflight_webp(modified, 147456)
    raw = webp_chunk(b"VP8L", b"\x2f\x00\x00\x00\x00")
    assert preflight_webp(raw, 147456) == (1, 1)
    with pytest.raises(ValueError):
        preflight_webp(raw[:-1] + b"\x01", 147456)
    with pytest.raises(ValueError, match="raster"):
        validate_inline_image(part("webp", raw), profile("webp"))


@pytest.mark.parametrize("kind", ["jpeg", "webp"])
def test_format_tools_schema_order_estimate_and_aggregate(kind):
    p = GoogleFeatureProfile(
        features=("inline_images", "function_tools", "json_schema"),
        combinations=(("inline_images", "function_tools", "json_schema"),),
        continuation_policy="unsigned",
        image_formats=(kind,),
        image_input_tokens=258,
        image_token_pricing=True,
    )
    schema = {"type": "object", "properties": {}, "required": [], "additionalProperties": False}
    image = part(kind, image_bytes(kind))
    body = {
        "model": "logical",
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": "before"},
                    image,
                    {"type": "input_text", "text": "after"},
                ],
            }
        ],
        "tools": [{"type": "function", "name": "f", "strict": True, "parameters": schema}],
        "text": {
            "format": {"type": "json_schema", "name": "result", "strict": True, "schema": schema}
        },
    }
    adapter = GoogleAiStudioAdapter(profile=p)
    assert adapter.check_request("responses", body) is None
    upstream = adapter.build_upstream_body(
        "responses", body, deployment="synthetic", default_output_tokens=100
    )
    assert [item["type"] for item in upstream["messages"][0]["content"]] == [
        "text",
        "image_url",
        "text",
    ]
    assert upstream["messages"][0]["content"][1]["image_url"]["url"] == image["image_url"]
    body["input"][0]["content"] = [image] * 5
    assert adapter.check_request("responses", body) is not None
