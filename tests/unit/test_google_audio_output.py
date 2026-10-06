"""Unattached native audio mapping and versioned actual SDK binary consumption."""

import base64

import pytest
from openai.types.responses import Response

from foundry_router.api.adapters.google_audio_output import GoogleAudioOutputAdapter
from foundry_router.config.google_features import GoogleFeatureProfile
from tests.unit.test_google_audio_output_config import profile
from tests.unit.test_google_output_wav import wav

BODY = {
    "model": "m",
    "input": "fixture",
    "foundry_audio_generation": {"version": 1, "format": "wav", "voice": "Kore"},
}


def adapter(**patch):
    return GoogleAudioOutputAdapter(profile=GoogleFeatureProfile(**{**profile(), **patch}))


def native(parts, finish="STOP"):
    return {
        "candidates": [{"content": {"role": "model", "parts": parts}, "finishReason": finish}],
        "usageMetadata": {"promptTokenCount": 4, "candidatesTokenCount": 2, "totalTokenCount": 6},
    }


def media():
    return {"inlineData": {"mimeType": "audio/wav", "data": base64.b64encode(wav(2)).decode()}}


@pytest.mark.parametrize("thinking", ["omit", "disable_zero"])
def test_native_format_voice_and_explicit_thinking_policy(thinking):
    result = adapter(audio_output_thinking_policy=thinking).build_upstream_body(
        "responses",
        {**BODY, "instructions": "style"},
        deployment="configured",
        default_output_tokens=1,
    )
    assert result["contents"] == [{"role": "user", "parts": [{"text": "fixture"}]}]
    assert result["systemInstruction"] == {"parts": [{"text": "style"}]}
    config = result["generationConfig"]
    assert config["responseModalities"] == ["AUDIO"] and config["maxOutputTokens"] == 2048
    assert config["responseFormat"] == {
        "audio": {"mimeType": "AUDIO_WAV", "delivery": "INLINE", "sampleRate": 24000}
    }
    assert config["speechConfig"] == {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": "Kore"}}}
    assert ("thinkingConfig" in config) == (thinking == "disable_zero")


def test_actual_sdk_consumes_root_audio_without_invented_output_item():
    result = adapter().translate_success(
        "responses",
        native([media()]),
        logical_model="m",
        request_body=BODY,
        metadata={"fixture": "owned"},
    )
    response = Response.model_validate(result.body)
    assert (
        response.status == "completed"
        and response.output == []
        and response.metadata == {"fixture": "owned"}
    )
    carrier = response.model_extra["foundry_generated_audio"]
    assert base64.b64decode(carrier["data"]) == wav(2)
    assert response.model_dump()["foundry_generated_audio"] == carrier
    assert response.usage.input_tokens == 4


@pytest.mark.parametrize("finish", ["MAX_TOKENS", "SAFETY"])
def test_length_and_refusal_never_complete_binary(finish):
    parts = [media()] if finish == "MAX_TOKENS" else []
    result = adapter().translate_success(
        "responses", native(parts, finish), logical_model="m", request_body=BODY
    )
    assert "foundry_generated_audio" not in result.body
    assert result.body["status"] in {"incomplete", "completed"}


@pytest.mark.parametrize(
    "parts",
    [
        [],
        [media(), media()],
        [{"text": "PRIVATE_OUTPUT"}],
        [{"inlineData": {"mimeType": "audio/l16", "data": "AAAA"}}],
        [{"inlineData": {"mimeType": "audio/wav", "data": "PRIVATE_OUTPUT"}}],
        [{**media(), "thoughtSignature": "PRIVATE_STATE"}],
    ],
)
def test_invalid_parts_or_state_cannot_be_projected(parts):
    with pytest.raises(ValueError):
        adapter().translate_success(
            "responses", native(parts), logical_model="m", request_body=BODY
        )


def test_unknown_envelope_rejects_before_decode(monkeypatch):
    def forbidden(*_args):
        pytest.fail("Invalid envelope cannot enter media decoder")

    monkeypatch.setattr(
        "foundry_router.api.adapters.google_audio_output.decode_output_wav", forbidden
    )
    with pytest.raises(ValueError):
        adapter().translate_success(
            "responses",
            {**native([media()]), "PRIVATE_UNKNOWN": "state"},
            logical_model="m",
            request_body=BODY,
        )


def test_audio_thinking_usage_is_not_discarded_or_relabelled():
    raw = native([media()])
    raw["usageMetadata"] = {
        "promptTokenCount": 4,
        "candidatesTokenCount": 2,
        "thoughtsTokenCount": 1,
        "totalTokenCount": 7,
    }
    with pytest.raises(ValueError, match="thinking"):
        adapter().translate_success("responses", raw, logical_model="m", request_body=BODY)


@pytest.mark.parametrize("finish", ["MAX_TOKENS", "SAFETY"])
@pytest.mark.parametrize("data", [None, "", 1])
def test_present_malformed_audio_is_not_confused_with_absent_artifact(finish, data):
    parts = [{"inlineData": {"mimeType": "audio/wav", "data": data}}]
    with pytest.raises(ValueError):
        adapter().translate_success(
            "responses", native(parts, finish), logical_model="m", request_body=BODY
        )


def test_blocked_audio_rejects_before_decode(monkeypatch):
    def forbidden(*_args):
        pytest.fail("Blocked artifact cannot enter decoder")

    monkeypatch.setattr(
        "foundry_router.api.adapters.google_audio_output.decode_output_wav", forbidden
    )
    with pytest.raises(ValueError):
        adapter().translate_success(
            "responses", native([media()], "SAFETY"), logical_model="m", request_body=BODY
        )
