"""Full generated-audio reserve retains seconds pricing independently of output tokens."""

from types import SimpleNamespace

import pytest

from foundry_router.config import PricingConfig
from foundry_router.config.google_features import GoogleFeatureProfile
from foundry_router.credit import estimate_request_cost
from tests.unit.test_google_audio_output import BODY
from tests.unit.test_google_audio_output_config import profile


def settings():
    return SimpleNamespace(
        models={"m": SimpleNamespace(backends={"g": 1})},
        backends={"g": SimpleNamespace(google_features=GoogleFeatureProfile(**profile()))},
    )


def test_seconds_fee_input_upperbound_and_total_output_reserve():
    config = settings()
    pricing = {
        "m": PricingConfig(
            input_per_million=10, output_per_million=30, audio_output_per_second=0.01
        )
    }
    estimate = estimate_request_cost(
        model="m", operation="responses", body=BODY, pricing=pricing, settings=config
    )
    assert estimate.input_tokens == len("fixture") + 64 and estimate.output_tokens == 2048
    assert estimate.estimated_cost_usd == pytest.approx(0.1 + 0.06144 + 0.00071)
    assert (
        estimate_request_cost(
            model="m",
            operation="responses",
            body={**BODY, "max_output_tokens": 1024},
            pricing=pricing,
            settings=config,
        )
        is None
    )


@pytest.mark.parametrize("price", [None, -1, float("nan"), True, 0.02])
def test_missing_invalid_or_conflicting_seconds_price_fails_closed(price):
    pricing = {
        "m": SimpleNamespace(
            input_per_million=10, output_per_million=30, audio_output_per_second=price
        )
    }
    assert (
        estimate_request_cost(
            model="m", operation="responses", body=BODY, pricing=pricing, settings=settings()
        )
        is None
    )


def test_free_audio_still_reserves_input_and_total_output_tokens():
    config = settings()
    config.backends["g"].google_features = GoogleFeatureProfile(
        **{**profile(), "audio_output_price_ceiling_usd_per_second": 0}
    )
    pricing = {
        "m": PricingConfig(input_per_million=0, output_per_million=0, audio_output_per_second=0)
    }
    estimate = estimate_request_cost(
        model="m", operation="responses", body=BODY, pricing=pricing, settings=config
    )
    assert (
        estimate.estimated_cost_usd == 0
        and estimate.input_tokens > 0
        and estimate.output_tokens == 2048
    )
