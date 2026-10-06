"""Exact standard generated image request recognition, without adapter dependencies."""

from typing import Any

_IMAGE_TOOL = {"type": "image_generation", "output_format": "png", "size": "1024x1024"}


def image_output_request(body: dict[str, Any]) -> bool:
    """Identify only the exact reviewed standard auto image-generation shape."""
    return body.get("tools") == [_IMAGE_TOOL]


def validate_image_output_request(body: dict[str, Any]) -> None:
    if (
        not image_output_request(body)
        or any(
            key in body
            for key in (
                "tool_choice",
                "parallel_tool_calls",
                "text",
                "foundry_provider_state",
            )
        )
        or body.get("stream", False) is not False
    ):
        raise ValueError("Unsupported generated image request")
