"""Unattached generated image projection consumes only worker-validated standard artifacts."""

import base64
import hashlib
from types import SimpleNamespace

import pytest
from openai.types.responses.response_output_item import ImageGenerationCall

from foundry_router.api.adapters.google_image_output import (
    project_image_output,
    validate_image_output_request,
)
from tests.unit.test_google_output_png import png


class FakeLease:
    delivery_deadline = None

    def bind_delivery_deadline(self, deadline):
        self.delivery_deadline = deadline

    async def inspect(self, raw, *, deadline):
        _ = deadline
        return SimpleNamespace(decoded_bytes=len(raw), digest=hashlib.sha256(raw).hexdigest())


def native(parts, finish="STOP"):
    return {"candidates": [{"content": {"role": "model", "parts": parts}, "finishReason": finish}]}


def artifact():
    return {"inlineData": {"mimeType": "image/png", "data": base64.b64encode(png()).decode()}}


async def test_actual_sdk_call_consumes_ordered_validated_artifact():
    raw = artifact()
    sanitized, items = await project_image_output(
        native([{"text": "before"}, raw, {"text": "after"}]), lease=FakeLease(), deadline=1
    )
    assert [x["type"] for x in items] == ["text", "image_generation_call", "text"]
    model = ImageGenerationCall.model_validate(items[1])
    assert base64.b64decode(model.result) == png()
    assert sanitized["candidates"][0]["content"]["parts"] == [{"text": "before"}, {"text": "after"}]


async def test_auto_text_only_and_length_never_complete_artifact():
    _, items = await project_image_output(
        native([{"text": "textonly"}]), lease=FakeLease(), deadline=1
    )
    assert items == ({"type": "text", "text": "textonly"},)
    _, items = await project_image_output(
        native([artifact()], "MAX_TOKENS"), lease=FakeLease(), deadline=1
    )
    assert not items


@pytest.mark.parametrize(
    "parts",
    [
        [artifact(), artifact()],
        [{"text": "x", "thoughtSignature": "private"}],
        [{"inlineData": {"mimeType": "image/jpeg", "data": "AAAA"}}],
        [{"inlineData": {"mimeType": "image/png", "data": "!!!"}}],
    ],
)
async def test_state_multiple_images_mime_and_encoding_reject(parts):
    with pytest.raises(ValueError):
        await project_image_output(native(parts), lease=FakeLease(), deadline=1)


def test_exact_auto_nonstream_public_shape():
    valid = {"tools": [{"type": "image_generation", "output_format": "png", "size": "1024x1024"}]}
    validate_image_output_request(valid)
    for patch in (
        {"stream": True},
        {"tool_choice": "required"},
        {"text": {}},
        {"parallel_tool_calls": False},
    ):
        with pytest.raises(ValueError):
            validate_image_output_request({**valid, **patch})


@pytest.mark.parametrize(
    "late",
    [
        artifact(),
        {"functionCall": {"id": "c", "name": "f", "args": {}}},
        {"inlineData": {"mimeType": "image/jpeg", "data": "AAAA"}},
    ],
)
async def test_entire_part_contract_rejects_before_worker(late):
    class RejectLease:
        async def inspect(self, *_args, **_kwargs):
            pytest.fail("worker must not start for invalid later part")

    with pytest.raises(ValueError):
        await project_image_output(native([artifact(), late]), lease=RejectLease(), deadline=1)
