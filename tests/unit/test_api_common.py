"""Unit tests for shared API request-intake bounds."""

from __future__ import annotations

import asyncio
import json

from fastapi import Request
from fastapi.responses import JSONResponse

from foundry_router.api.common import request_body

MAX_BODY_BYTES = 1024


def _make_request(*, headers: dict[str, str], chunks: list[bytes]) -> Request:
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/openai/v1/responses",
        "headers": [
            (key.lower().encode("latin-1"), value.encode("latin-1"))
            for key, value in headers.items()
        ],
    }
    remaining = list(chunks)

    async def receive() -> dict:
        if not remaining:
            return {"type": "http.request", "body": b"", "more_body": False}
        chunk = remaining.pop(0)
        return {"type": "http.request", "body": chunk, "more_body": bool(remaining)}

    return Request(scope, receive)


class TestRequestBodyBounds:
    def test_rejects_oversized_content_length_before_reading_stream(self) -> None:
        request = _make_request(
            headers={
                "content-type": "application/json",
                "content-length": str(MAX_BODY_BYTES * 10),
            },
            chunks=[b'{"model": "gpt-4"}'],
        )
        result = asyncio.run(request_body(request, "responses", max_body_bytes=MAX_BODY_BYTES))
        assert isinstance(result, JSONResponse)
        assert result.status_code == 413

    def test_rejects_oversized_body_without_content_length(self) -> None:
        payload = json.dumps({"model": "gpt-4", "input": "x" * (MAX_BODY_BYTES * 2)}).encode(
            "utf-8"
        )
        chunk_size = 128
        chunks = [payload[i : i + chunk_size] for i in range(0, len(payload), chunk_size)]
        request = _make_request(
            headers={"content-type": "application/json"},
            chunks=chunks,
        )
        result = asyncio.run(request_body(request, "responses", max_body_bytes=MAX_BODY_BYTES))
        assert isinstance(result, JSONResponse)
        assert result.status_code == 413

    def test_accepts_body_within_limit(self) -> None:
        payload = json.dumps({"model": "gpt-4", "input": "hello"}).encode("utf-8")
        request = _make_request(
            headers={
                "content-type": "application/json",
                "content-length": str(len(payload)),
            },
            chunks=[payload],
        )
        result = asyncio.run(request_body(request, "responses", max_body_bytes=MAX_BODY_BYTES))
        assert result == {"model": "gpt-4", "input": "hello"}

    def test_invalid_content_length_header_rejected(self) -> None:
        request = _make_request(
            headers={"content-type": "application/json", "content-length": "not-a-number"},
            chunks=[b'{"model": "gpt-4"}'],
        )
        result = asyncio.run(request_body(request, "responses", max_body_bytes=MAX_BODY_BYTES))
        assert isinstance(result, JSONResponse)
        assert result.status_code == 400
