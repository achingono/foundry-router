"""Bounded thinkingLevel path: validation matrix, exact bodies, strict thoughts."""

import json

import pytest

from foundry_router.api.adapters.google_native import (
    GoogleNativeAdapter,
    native_usage,
    unsigned_ordinary_profile,
)
from foundry_router.config.google_features import GoogleFeatureProfile


def profile(**overrides):
    return GoogleFeatureProfile(**overrides)


def test_level_text_only_profile_validates():
    for level in ("minimal", "low"):
        checked = profile(native_thinking_disabled=False, native_thinking_level=level)
        assert checked.native_thinking_level == level


def test_level_matrix_rejects():
    base = {"native_thinking_disabled": False, "native_thinking_level": "minimal"}
    with pytest.raises(ValueError, match="text-only"):
        profile(**{**base, "native_thinking_disabled": True})
    with pytest.raises(ValueError, match="text-only"):
        profile(**{**base, "native_thinking_budget": 8})
    with pytest.raises(ValueError, match="text-only"):
        profile(
            features=("function_tools",),
            continuation_policy="sealed_native",
            native_thinking_disabled=False,
            native_thinking_budget=8,
            thought_token_pricing=True,
            signature_input_token_bound=100000,
            native_thinking_level="minimal",
        )
    with pytest.raises(ValueError, match="explicit continuation policy"):
        profile(**{**base, "features": ("function_tools",)})
    with pytest.raises(ValueError, match="text-only"):
        profile(**{**base, "features": ("json_schema",)})
    with pytest.raises(ValueError, match="text-only"):
        profile(
            **{
                **base,
                "features": ("inline_pdfs",),
                "pdf_input_tokens_per_page": 258,
                "pdf_native_text_tokens_per_page": 65536,
                "pdf_token_pricing": True,
            }
        )
    with pytest.raises(ValueError, match="minimal.*low"):
        profile(native_thinking_disabled=False, native_thinking_level="medium")
    with pytest.raises(ValueError, match="sealed native policy|thinking budgets"):
        profile(native_thinking_budget=8)


def test_defaults_and_budget_zero_canonical_still_load():
    assert profile().native_thinking_level is None
    assert profile(native_thinking_disabled=True).native_thinking_level is None


def test_backend_native_accepts_level_rejects_shapeless():
    from foundry_router.config import BackendConfig

    endpoint = "https://generativelanguage.googleapis.com"
    level = BackendConfig(
        provider="google_ai_studio",
        api_surface="native",
        endpoint=endpoint,
        credential="synthetic",
        deployment="configured",
        google_features={
            "native_thinking_disabled": False,
            "native_thinking_level": "minimal",
        },
    )
    assert level.google_features.native_thinking_level == "minimal"
    with pytest.raises(ValueError, match="thinking-disable affirmation"):
        BackendConfig(
            provider="google_ai_studio",
            api_surface="native",
            endpoint=endpoint,
            credential="synthetic",
            deployment="configured",
            google_features={"native_thinking_disabled": False},
        )


def _adapter(**overrides):
    return GoogleNativeAdapter(profile=profile(**overrides))


def test_check_request_level_path_and_shapeless_rejection():
    body = {"model": "m", "input": "fixture", "max_output_tokens": 10}
    assert (
        _adapter(native_thinking_disabled=False, native_thinking_level="minimal").check_request(
            "responses", body
        )
        is None
    )
    assert _adapter(native_thinking_disabled=False).check_request("responses", body) is not None
    bypassed = profile(native_thinking_disabled=True).model_copy(
        update={"native_thinking_disabled": False, "native_thinking_budget": 8}
    )
    assert GoogleNativeAdapter(profile=bypassed).check_request("responses", body) is not None
    with pytest.raises(ValueError, match="sealed native policy|thinking budgets"):
        profile(native_thinking_disabled=False, native_thinking_budget=8)


def test_build_upstream_body_exact_thinking_shapes():
    body = {"model": "m", "input": "fixture", "max_output_tokens": 10}
    level_body = _adapter(
        native_thinking_disabled=False, native_thinking_level="low"
    ).build_upstream_body("responses", body, deployment="d", default_output_tokens=10)
    assert level_body["generationConfig"]["thinkingConfig"] == {"thinkingLevel": "low"}
    budget_body = _adapter(native_thinking_disabled=True).build_upstream_body(
        "responses", body, deployment="d", default_output_tokens=10
    )
    assert budget_body["generationConfig"]["thinkingConfig"] == {"thinkingBudget": 0}


def test_strict_usage_level_accepts_thoughts_budget_rejects():
    payload = {
        "usageMetadata": {
            "promptTokenCount": 10,
            "candidatesTokenCount": 3,
            "thoughtsTokenCount": 5,
            "totalTokenCount": 18,
        }
    }
    prompt, output = native_usage(payload, strict=True, accept_thoughts=True)
    assert (prompt, output) == (10, 8)
    with pytest.raises(ValueError, match="disabled"):
        native_usage(payload, strict=True)
    tools = {
        "usageMetadata": {
            "promptTokenCount": 10,
            "candidatesTokenCount": 3,
            "toolUsePromptTokenCount": 2,
            "totalTokenCount": 13,
        }
    }
    with pytest.raises(ValueError, match="disabled"):
        native_usage(tools, strict=True, accept_thoughts=True)


def test_translate_success_level_accepts_thought_usage():
    adapter = _adapter(native_thinking_disabled=False, native_thinking_level="minimal")
    translated = adapter.translate_success(
        "responses",
        {
            "candidates": [
                {
                    "content": {"role": "model", "parts": [{"text": "ready"}]},
                    "finishReason": "STOP",
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 10,
                "candidatesTokenCount": 3,
                "thoughtsTokenCount": 5,
                "totalTokenCount": 18,
            },
        },
        logical_model="m",
    )
    assert translated.input_tokens == 10 and translated.output_tokens == 8


def test_ordinary_delegate_strips_level():
    sealed = profile(
        features=("function_tools",),
        continuation_policy="sealed_native",
        native_thinking_disabled=False,
        native_thinking_budget=8,
        thought_token_pricing=True,
        signature_input_token_bound=100000,
    )
    ordinary = unsigned_ordinary_profile(sealed)
    assert ordinary.native_thinking_level is None
    assert ordinary.native_thinking_disabled is True
    assert ordinary.continuation_policy == "unsigned"
    adapter = GoogleNativeAdapter(profile=ordinary)
    body = {"model": "m", "input": "fixture", "max_output_tokens": 10}
    built = adapter.build_upstream_body("responses", body, deployment="d", default_output_tokens=10)
    assert built["generationConfig"]["thinkingConfig"] == {"thinkingBudget": 0}


def test_thought_signature_parts_dropped_after_usage_capture():
    adapter = _adapter(native_thinking_disabled=False, native_thinking_level="minimal")
    translated = adapter.translate_success(
        "responses",
        {
            "candidates": [
                {
                    "content": {
                        "role": "model",
                        "parts": [{"text": "Ready.", "thoughtSignature": "c2ln"}],
                    },
                    "finishReason": "STOP",
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 7,
                "candidatesTokenCount": 2,
                "totalTokenCount": 9,
            },
        },
        logical_model="m",
    )
    assert translated.input_tokens == 7 and translated.output_tokens == 2
    texts = [
        part.get("text")
        for item in translated.body["output"]
        if isinstance(item, dict) and item.get("type") == "message"
        for part in item.get("content", [])
        if isinstance(part, dict)
    ]
    assert texts == ["Ready."]
    assert "c2ln" not in json.dumps(translated.body)


def test_empty_or_missing_signature_rejected():
    from foundry_router.api.adapters.google_native import _native_output

    for parts in (
        [{"text": "Ready.", "thoughtSignature": ""}],
        [{"text": "Ready.", "thoughtSignature": None}],
        [{"thoughtSignature": "c2ln"}],
    ):
        with pytest.raises(ValueError, match="Unsupported native output"):
            _native_output(
                {
                    "candidates": [
                        {
                            "content": {"role": "model", "parts": parts},
                            "finishReason": "STOP",
                        }
                    ]
                }
            )
