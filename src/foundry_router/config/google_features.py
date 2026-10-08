"""Default-off, operator-declared Google feature and resource bounds."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

GoogleFeature = Literal[
    "function_tools",
    "parallel_calls",
    "json_object",
    "json_schema",
    "inline_images",
    "inline_pdfs",
    "inline_audio",
    "inline_video",
    "image_output",
    "audio_output",
]
_MIN_COMBINATION_SIZE = 2
_MAX_AUDIO_VOICES = 30


class GoogleFeatureProfile(BaseModel):
    """Configured support is not evidence of live provider compatibility."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    features: tuple[GoogleFeature, ...] = ()
    combinations: tuple[tuple[GoogleFeature, ...], ...] = ()
    continuation_policy: Literal["disabled", "unsigned", "sealed_native"] = "disabled"
    max_tools: int = Field(default=16, ge=1, le=32)
    max_history_items: int = Field(default=128, ge=1, le=256)
    max_argument_bytes: int = Field(default=65536, ge=128, le=262144)
    max_result_bytes: int = Field(default=65536, ge=128, le=262144)
    max_images: int = Field(default=4, ge=1, le=8)
    image_formats: tuple[Literal["png", "jpeg", "webp"], ...] = ("png",)
    max_image_bytes: int = Field(default=262144, ge=128, le=524288)
    max_total_image_bytes: int = Field(default=524288, ge=128, le=1048576)
    max_image_pixels: int = Field(default=147456, ge=1, le=147456)
    max_jpeg_total_pixels: int = Field(default=32768, ge=1, le=32768)
    image_input_tokens: int | None = Field(default=None, ge=258, le=100000)
    image_token_pricing: bool = False
    native_thinking_disabled: bool = False
    native_thinking_budget: int | None = Field(default=None, ge=0, le=8192, strict=True)
    native_thinking_level: Literal["minimal", "low"] | None = None
    thought_token_pricing: bool = False
    signature_input_token_bound: int | None = Field(
        default=None, ge=100000, le=2000000, strict=True
    )
    max_pdfs: int = Field(default=4, ge=1, le=4)
    max_pdf_bytes: int = Field(default=65536, ge=128, le=65536)
    max_total_pdf_bytes: int = Field(default=131072, ge=128, le=131072)
    max_pdf_pages: int = Field(default=4, ge=1, le=4)
    pdf_input_tokens_per_page: int | None = Field(default=None, ge=258, le=100000)
    pdf_native_text_tokens_per_page: int | None = Field(default=None, ge=65536, le=1000000)
    pdf_token_pricing: bool = False

    max_audio_files: int = Field(default=2, ge=1, le=2)
    max_audio_bytes: int = Field(default=320044, ge=46, le=320044)
    max_total_audio_bytes: int = Field(default=640088, ge=46, le=640088)
    max_audio_seconds: int = Field(default=10, ge=1, le=10)
    max_total_audio_seconds: int = Field(default=20, ge=1, le=20)
    audio_input_tokens_per_second: int | None = Field(default=None, ge=32, le=10000)
    audio_token_pricing: bool = False
    audio_tpm_tokens: bool = False

    max_video_files: int = Field(default=2, ge=1, le=2)
    max_video_bytes: int = Field(default=65536, ge=236, le=65536)
    max_total_video_bytes: int = Field(default=131072, ge=236, le=131072)
    max_video_frames: int = Field(default=4, ge=1, le=4)
    max_total_video_frames: int = Field(default=8, ge=1, le=8)
    max_video_pixels: int = Field(default=4096, ge=1, le=4096)
    video_input_tokens_per_frame: int | None = Field(default=None, ge=258, le=100000)
    video_token_pricing: bool = False
    video_tpm_tokens: bool = False

    generated_output_tokens_bound: int | None = Field(default=None, ge=2048, le=32768, strict=True)
    image_output_price_ceiling_usd: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    image_output_input_token_pricing: bool = False
    image_output_quota_via_rpm: bool = False
    image_output_input_tpm_tokens: bool = False
    image_output_ipm: int | None = Field(default=None, ge=1, le=100000, strict=True)
    audio_output_voices: tuple[str, ...] = ()
    audio_output_thinking_policy: Literal["omit", "disable_zero"] | None = None
    audio_output_thinking_affirmed: bool = False
    audio_output_price_ceiling_usd_per_second: float | None = Field(
        default=None, ge=0, allow_inf_nan=False
    )
    audio_output_input_token_pricing: bool = False
    audio_output_quota_via_rpm: bool = False
    audio_output_input_tpm_tokens: bool = False
    audio_output_rpm: int | None = Field(default=None, ge=1, le=100000, strict=True)

    @model_validator(mode="after")
    def validate_features(self) -> GoogleFeatureProfile:
        enabled = set(self.features)
        self._validate_audio_output(enabled)
        if not self.image_formats or len(set(self.image_formats)) != len(self.image_formats):
            raise ValueError("Image formats must be nonempty and unique")
        if len(enabled) != len(self.features):
            raise ValueError("Google features must be unique")
        if "parallel_calls" in enabled and "function_tools" not in enabled:
            raise ValueError("Parallel calls require function tools")
        if ("function_tools" in enabled) != (
            self.continuation_policy in {"unsigned", "sealed_native"}
        ):
            raise ValueError("Function tools require an explicit continuation policy")
        if "inline_images" in enabled and (
            self.image_input_tokens is None or not self.image_token_pricing
        ):
            raise ValueError("Inline images require a token ceiling and token-price affirmation")
        if "inline_pdfs" in enabled and (
            self.pdf_input_tokens_per_page is None
            or self.pdf_native_text_tokens_per_page is None
            or not self.pdf_token_pricing
        ):
            raise ValueError("Inline PDFs require visual/text ceilings and token-price affirmation")
        if "image_output" in enabled and (
            self.generated_output_tokens_bound is None
            or self.image_output_price_ceiling_usd is None
            or not self.image_output_input_token_pricing
            or not self.image_output_quota_via_rpm
            or not self.image_output_input_tpm_tokens
            or self.image_output_ipm is None
            or not self.native_thinking_disabled
            or self.continuation_policy != "disabled"
            or enabled - {"image_output", "inline_images"}
        ):
            raise ValueError("Image output requires complete finite pricing/quota/native profile")
        if "inline_video" in enabled and (
            self.video_input_tokens_per_frame is None
            or not self.video_token_pricing
            or not self.video_tpm_tokens
        ):
            raise ValueError("Inline video requires token ceiling, pricing and TPM affirmations")
        if "inline_audio" in enabled and (
            self.audio_input_tokens_per_second is None
            or not self.audio_token_pricing
            or not self.audio_tpm_tokens
        ):
            raise ValueError("Inline audio requires token ceiling, pricing and TPM affirmations")
        if self.continuation_policy == "sealed_native" and (
            self.native_thinking_disabled
            or self.native_thinking_budget is None
            or not self.thought_token_pricing
            or self.signature_input_token_bound is None
        ):
            raise ValueError(
                "Sealed native policy requires thinking/signature ceilings and token pricing"
            )
        self._validate_thinking_shape(enabled)
        self._validate_combinations(enabled)
        return self

    def _validate_thinking_shape(self, enabled: set[GoogleFeature]) -> None:
        """Enforce the thinking-configuration matrix (level/budget/disabled)."""
        if self.native_thinking_level is not None and (
            # Text-only track: no tools, structured output, media, or sealed policy.
            # An empty feature set is required (audio/image exclusions below are
            # then implied, but stated for the audit trail).
            self.native_thinking_disabled
            or self.native_thinking_budget is not None
            or self.continuation_policy == "sealed_native"
            or enabled
            or "audio_output" in enabled
            or "image_output" in enabled
        ):
            raise ValueError("Thinking levels require an enabled-thinking text-only profile")
        if self.native_thinking_budget is not None and self.continuation_policy != "sealed_native":
            raise ValueError("Thinking budgets require the sealed native policy")

    def _validate_combinations(self, enabled: set[GoogleFeature]) -> None:
        seen: set[frozenset[str]] = set()
        for combination in self.combinations:
            members = frozenset(combination)
            if (
                len(members) != len(combination)
                or len(members) < _MIN_COMBINATION_SIZE
                or not members <= enabled
                or members in seen
            ):
                raise ValueError("Google combinations must be unique enabled feature sets")
            seen.add(members)

    def _validate_audio_output(self, enabled: set[GoogleFeature]) -> None:
        if "audio_output" in enabled and (
            enabled != {"audio_output"}
            or self.continuation_policy != "disabled"
            or self.generated_output_tokens_bound is None
            or self.audio_output_thinking_policy is None
            or not self.audio_output_thinking_affirmed
            or self.audio_output_price_ceiling_usd_per_second is None
            or not self.audio_output_input_token_pricing
            or not self.audio_output_quota_via_rpm
            or not self.audio_output_input_tpm_tokens
            or self.audio_output_rpm is None
            or not 1 <= len(self.audio_output_voices) <= _MAX_AUDIO_VOICES
            or len(set(self.audio_output_voices)) != len(self.audio_output_voices)
            or any(
                re.fullmatch(r"[A-Za-z][A-Za-z0-9]{0,31}", voice) is None
                for voice in self.audio_output_voices
            )
        ):
            raise ValueError(
                "Audio output requires a complete finite native pricing/quota/voice profile"
            )

    def permits(self, requested: set[str]) -> bool:
        if not requested <= set(self.features):
            return False
        return len(requested) <= 1 or frozenset(requested) in {
            frozenset(combination) for combination in self.combinations
        }
