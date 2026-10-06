"""Finite WAV structural bounds, prepared identity and pricing configuration."""

import base64
import struct
from dataclasses import replace

import pytest
from pydantic import ValidationError

from foundry_router.api.google_audio import prepare_audio, validate_prepared_audio
from foundry_router.api.google_pdf import PdfPreparationError, pdf_parts
from foundry_router.config import BackendConfig
from foundry_router.config.google_features import GoogleFeatureProfile


def wav_part(frames=16000):
    raw = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + frames * 2,
        b"WAVE",
        b"fmt ",
        16,
        1,
        1,
        16000,
        32000,
        2,
        16,
        b"data",
        frames * 2,
    )
    raw += b"\0" * (frames * 2)
    return {
        "type": "input_file",
        "filename": "fixture.wav",
        "file_data": "data:audio/wav;base64," + base64.b64encode(raw).decode(),
    }


def audio_body(*parts):
    return {"model": "m", "input": [{"role": "user", "content": list(parts)}]}


def audio_profile(**patch):
    return GoogleFeatureProfile(
        features=("inline_audio",),
        audio_input_tokens_per_second=32,
        audio_token_pricing=True,
        audio_tpm_tokens=True,
        **patch,
    )


def test_maxima_and_pdf_dispatch():
    body = audio_body(wav_part(160000), wav_part(160000))
    facts = prepare_audio(body)
    assert sum(item.frames for item in facts) == 320000
    assert sum(item.decoded_bytes for item in facts) == 640088
    assert pdf_parts(body) == []
    validate_prepared_audio(body, facts, audio_profile())
    for profile in (
        audio_profile(max_audio_files=1),
        audio_profile(max_audio_seconds=9),
        audio_profile(max_total_audio_seconds=19),
        audio_profile(max_audio_bytes=320043),
        audio_profile(max_total_audio_bytes=640087),
    ):
        with pytest.raises(ValueError):
            validate_prepared_audio(body, facts, profile)


@pytest.mark.parametrize(
    "offset,value",
    [
        (0, 0),
        (4, 1),
        (8, 0),
        (12, 0),
        (16, 18),
        (20, 3),
        (22, 2),
        (24, 1),
        (28, 1),
        (32, 4),
        (34, 8),
        (36, 0),
        (40, 1),
    ],
)
def test_header_rejects_mislabeled_compressed_chunks_and_lengths(offset, value):
    part = wav_part()
    raw = bytearray(base64.b64decode(part["file_data"].split(",", 1)[1]))
    raw[offset] = value
    part["file_data"] = "data:audio/wav;base64," + base64.b64encode(raw).decode()
    with pytest.raises(PdfPreparationError):
        prepare_audio(audio_body(part))


@pytest.mark.parametrize(
    "patch",
    [
        {"filename": None},
        {"filename": "../a.wav"},
        {"filename": "a.WAV"},
        {"filename": "é.wav"},
        {"file_id": "id"},
        {"file_data": "data:audio/wav;base64,!!!"},
    ],
)
def test_shape_rejects(patch):
    with pytest.raises(PdfPreparationError):
        prepare_audio(audio_body({**wav_part(), **patch}))


def test_history_count_placement_empty_and_mutation():
    for body in (
        audio_body(wav_part(), wav_part(), wav_part()),
        audio_body(wav_part(0)),
        audio_body(wav_part(160001)),
        {"input": [{"role": "assistant", "content": [wav_part()]}]},
    ):
        with pytest.raises(PdfPreparationError):
            prepare_audio(body)
    body = audio_body(wav_part())
    facts = prepare_audio(body)
    with pytest.raises(ValueError):
        validate_prepared_audio(body, (replace(facts[0], digest="changed"),), audio_profile())
    body["input"][0]["content"][0] = wav_part(2)
    with pytest.raises(ValueError):
        validate_prepared_audio(body, facts, audio_profile())


def test_optional_filename_and_noncanonical_padding():
    part = wav_part(1)
    part.pop("filename")
    assert prepare_audio(audio_body(part))[0].frames == 1
    part["file_data"] += "="
    with pytest.raises(PdfPreparationError):
        prepare_audio(audio_body(part))


@pytest.mark.parametrize(
    "field,value",
    [
        ("audio_input_tokens_per_second", None),
        ("audio_token_pricing", False),
        ("audio_tpm_tokens", False),
    ],
)
def test_required_operator_affirmations(field, value):
    with pytest.raises(ValidationError):
        GoogleFeatureProfile(**{**audio_profile().model_dump(), field: value})


def test_audio_native_surface_required():
    with pytest.raises(ValidationError):
        BackendConfig(
            provider="google_ai_studio",
            endpoint="https://audio.example.test",
            credential="synthetic",
            deployment="configured",
            google_features=audio_profile(),
        )
