"""Generated image reserves preserve the separate image price on every billable outcome."""

from types import SimpleNamespace

import pytest

from foundry_router.credit import estimate_generated_image_request, generated_image_billable_cost


def test_separate_price_and_total_output_bound_retained():
    pricing = SimpleNamespace(input_per_million=10, output_per_million=30)
    estimate = estimate_generated_image_request(
        body={"input": "fixture"},
        model_pricing=pricing,
        total_output_tokens=2048,
        image_price_ceiling_usd=0.2,
    )
    assert estimate.output_tokens == 2048 and estimate.estimated_cost_usd > 0.2 + 0.06144
    assert generated_image_billable_cost(estimate) == estimate.estimated_cost_usd
    # Actual text/image aggregate tokens do not enter this settlement helper.
    assert estimate.input_tokens >= len("fixture")


@pytest.mark.parametrize(
    "bound,price",
    [
        (2047, 0.2),
        (32769, 0.2),
        (True, 0.2),
        (2048, -1),
        (2048, float("nan")),
        (2048, float("inf")),
        (2048, True),
    ],
)
def test_invalid_bound_or_image_price_fails_closed(bound, price):
    assert (
        estimate_generated_image_request(
            body={"input": "fixture"},
            model_pricing=SimpleNamespace(input_per_million=10, output_per_million=30),
            total_output_tokens=bound,
            image_price_ceiling_usd=price,
        )
        is None
    )


def test_free_still_has_finite_token_reservations_and_conflicting_ceiling_rejects():
    pricing = SimpleNamespace(input_per_million=0, output_per_million=0)
    estimate = estimate_generated_image_request(
        body={"input": "fixture"},
        model_pricing=pricing,
        total_output_tokens=2048,
        image_price_ceiling_usd=0,
    )
    assert (
        estimate.input_tokens > 0
        and estimate.output_tokens == 2048
        and estimate.estimated_cost_usd == 0
    )
    assert (
        estimate_generated_image_request(
            body={"input": "fixture", "max_output_tokens": 1024},
            model_pricing=pricing,
            total_output_tokens=2048,
            image_price_ceiling_usd=0,
        )
        is None
    )


@pytest.mark.parametrize(
    "pricing",
    [
        SimpleNamespace(),
        SimpleNamespace(input_per_million=None, output_per_million=0),
        SimpleNamespace(input_per_million=True, output_per_million=0),
    ],
)
def test_missing_pricing_is_not_implicitly_free(pricing):
    assert (
        estimate_generated_image_request(
            body={"input": "fixture"},
            model_pricing=pricing,
            total_output_tokens=2048,
            image_price_ceiling_usd=0,
        )
        is None
    )


def test_invalid_input_cannot_be_offset_by_instruction_tokens():
    assert (
        estimate_generated_image_request(
            body={"input": object(), "instructions": "x" * 100},
            model_pricing=SimpleNamespace(input_per_million=10, output_per_million=30),
            total_output_tokens=2048,
            image_price_ceiling_usd=0.2,
        )
        is None
    )


def test_float_output_ceiling_rejects():
    assert (
        estimate_generated_image_request(
            body={"input": "fixture", "max_output_tokens": 2048.0},
            model_pricing=SimpleNamespace(input_per_million=0, output_per_million=0),
            total_output_tokens=2048,
            image_price_ceiling_usd=0,
        )
        is None
    )


def test_input_images_and_unicode_instructions_use_additive_ceilings():
    pricing = SimpleNamespace(input_per_million=10, output_per_million=30, image_input_tokens=258)
    body = {
        "input": [{"role": "user", "content": [{"type": "input_image", "image_url": "opaque"}]}],
        "instructions": "é" * 100,
    }
    estimate = estimate_generated_image_request(
        body=body, model_pricing=pricing, total_output_tokens=2048, image_price_ceiling_usd=0.2
    )
    assert estimate.input_tokens >= 274 + 200


def test_azure_image_tool_preserves_existing_estimate_path():
    from foundry_router.config.google_features import GoogleFeatureProfile
    from foundry_router.credit import estimate_request_cost

    settings = SimpleNamespace(
        models={"m": SimpleNamespace(backends={"azure": 1})},
        backends={"azure": SimpleNamespace(google_features=GoogleFeatureProfile())},
    )
    pricing = {"m": SimpleNamespace(input_per_million=10, output_per_million=30)}
    body = {
        "input": "fixture",
        "tools": [{"type": "image_generation", "output_format": "png", "size": "1024x1024"}],
    }
    actual = estimate_request_cost(
        model="m", operation="responses", body=body, pricing=pricing, settings=settings
    )
    legacy = estimate_request_cost(model="m", operation="responses", body=body, pricing=pricing)
    assert actual is not None and actual == legacy
