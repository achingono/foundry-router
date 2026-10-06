"""Generated audio validates finite actual PCM container rather than MIME labels."""

import base64
import struct

import pytest

from foundry_router.api.google_output_wav import (
    decode_output_wav,
    inspect_output_wav,
    output_wav_ready,
)


def wav(size=480000):
    return (
        struct.pack(
            "<4sI4s4sIHHIIHH4sI",
            b"RIFF",
            36 + size,
            b"WAVE",
            b"fmt ",
            16,
            1,
            1,
            24000,
            48000,
            2,
            16,
            b"data",
            size,
        )
        + b"\0" * size
    )


@pytest.mark.parametrize("size", [2, 480000])
def test_finite_duration_and_exact_boundary(size):
    raw = wav(size)
    decoded, facts = decode_output_wav(base64.b64encode(raw).decode())
    assert decoded == raw and facts.frames == size // 2 and facts.decoded_bytes == 44 + size
    assert output_wav_ready()


@pytest.mark.parametrize(
    "raw",
    [
        wav(1),
        wav(480002),
        wav() + b"tail",
        wav()[:43],
        b"PRIVATE_MEDIA",
        wav().replace(b"WAVE", b"AVI ", 1),
    ],
)
def test_invalid_container_boundaries(raw):
    with pytest.raises(ValueError):
        inspect_output_wav(raw)


@pytest.mark.parametrize(
    "offset,value", [(20, 3), (22, 2), (24, 16000), (28, 32000), (32, 4), (34, 8)]
)
def test_codec_channel_rate_alignment_and_width_are_exact(offset, value):
    raw = bytearray(wav(2))
    struct.pack_into("<I" if offset in (24, 28) else "<H", raw, offset, value)
    with pytest.raises(ValueError):
        inspect_output_wav(bytes(raw))


@pytest.mark.parametrize("encoded", ["!", "A" * 640061, "", None])
def test_invalid_encoding_never_becomes_completed_artifact(encoded):
    with pytest.raises(ValueError):
        decode_output_wav(encoded)
