"""Canonical raw DIB AVI containers and resource/identity/config bounds."""

import base64
import struct
from dataclasses import replace

import pytest
from pydantic import ValidationError

from foundry_router.api.google_pdf import PdfPreparationError, pdf_parts
from foundry_router.api.google_video import inspect_video, prepare_video, validate_prepared_video
from foundry_router.config.google_features import GoogleFeatureProfile


def chunk(kind, data):
    return kind + struct.pack("<I", len(data)) + data


def avi(frames=4, width=64, height=64):
    stride = ((width * 3 + 3) // 4) * 4
    size = stride * height
    avih = struct.pack("<14I", 1000000, size, 0, 0, frames, 0, 1, size, width, height, 0, 0, 0, 0)
    strh = struct.pack(
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
        size,
        0xFFFFFFFF,
        0,
        0,
        0,
        width,
        height,
    )
    strf = struct.pack("<IiiHHIIiiII", 40, width, height, 1, 24, 0, size, 0, 0, 0, 0)
    hdrl = chunk(
        b"LIST",
        b"hdrl"
        + chunk(b"avih", avih)
        + chunk(b"LIST", b"strl" + chunk(b"strh", strh) + chunk(b"strf", strf)),
    )
    movi = chunk(b"LIST", b"movi" + chunk(b"00db", b"\0" * size) * frames)
    return chunk(b"RIFF", b"AVI " + hdrl + movi)


def video_part(raw=None):
    return {
        "type": "input_file",
        "filename": "fixture.avi",
        "file_data": "data:video/avi;base64,"
        + base64.b64encode(avi() if raw is None else raw).decode(),
    }


def video_body(*parts):
    return {"model": "m", "input": [{"role": "user", "content": list(parts)}]}


def video_profile(**patch):
    return GoogleFeatureProfile(
        features=("inline_video",),
        video_input_tokens_per_frame=258,
        video_token_pricing=True,
        video_tpm_tokens=True,
        **patch,
    )


def test_maximum_and_candidate_caps():
    body = video_body(video_part(), video_part())
    entries = prepare_video(body)
    assert sum(e.frames for e in entries) == 8 and pdf_parts(body) == []
    validate_prepared_video(body, entries, video_profile())
    for patch in (
        {"max_video_files": 1},
        {"max_video_frames": 3},
        {"max_total_video_frames": 7},
        {"max_video_pixels": 4095},
        {"max_video_bytes": len(avi()) - 1},
        {"max_total_video_bytes": 2 * len(avi()) - 1},
    ):
        with pytest.raises(ValueError):
            validate_prepared_video(body, entries, video_profile(**patch))
    with pytest.raises(ValueError):
        validate_prepared_video(
            body, (replace(entries[0], digest="bad"), entries[1]), video_profile()
        )


@pytest.mark.parametrize(
    "offset",
    [
        0,
        4,
        8,
        12,
        16,
        20,
        24,
        28,
        32,
        36,
        40,
        44,
        48,
        52,
        56,
        60,
        64,
        68,
        72,
        76,
        80,
        84,
        88,
        92,
        96,
        100,
        104,
        108,
        112,
        116,
        120,
        124,
        128,
        132,
        136,
        140,
        144,
        148,
        152,
        156,
        160,
        164,
        168,
        172,
        176,
        180,
        184,
        188,
        192,
        196,
        200,
        204,
        208,
        212,
        216,
        220,
        224,
    ],
)
def test_header_mutations_fail_closed(offset):
    raw = bytearray(avi())
    raw[offset] ^= 1
    with pytest.raises(PdfPreparationError):
        prepare_video(video_body(video_part(raw)))


def test_trailing_empty_timing_dimensions_padding_and_shape():
    for raw in (avi() + b"\0\0", avi(0), avi(5), avi(width=65), b"RIFF"):
        with pytest.raises(PdfPreparationError):
            prepare_video(video_body(video_part(raw)))
    assert inspect_video(avi(1, 1, 1)) == (1, 1, 1)
    raw = bytearray(avi(1, 1, 1))
    raw[-1] = 1
    with pytest.raises(ValueError):
        inspect_video(bytes(raw))
    for patch in (
        {"filename": None},
        {"filename": "../f.avi"},
        {"file_id": "x"},
        {"videoMetadata": {"fps": 24}},
    ):
        with pytest.raises(PdfPreparationError):
            prepare_video(video_body({**video_part(), **patch}))
    with pytest.raises(PdfPreparationError):
        prepare_video(video_body(video_part(), video_part(), video_part()))
    part = video_part()
    part.pop("filename")
    assert prepare_video(video_body(part))[0].frames == 4


@pytest.mark.parametrize(
    "field,value",
    [
        ("video_input_tokens_per_frame", None),
        ("video_token_pricing", False),
        ("video_tpm_tokens", False),
    ],
)
def test_required_affirmations(field, value):
    with pytest.raises(ValidationError):
        GoogleFeatureProfile(**{**video_profile().model_dump(), field: value})
