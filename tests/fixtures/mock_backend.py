"""Mock Foundry backend server for integration testing."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse

app = FastAPI(title="Mock Foundry Backend")


@app.post("/openai/deployments/{deployment}/chat/completions")
async def chat_completions(deployment: str, request: Request) -> Response:
    body = await request.json()
    stream = body.get("stream", False)

    if stream:

        async def generate():
            yield 'data: {"id": "chatcmpl-test", "object": "chat.completion.chunk", "choices": [{"delta": {"content": "Hello"}, "index": 0}]}\n\n'
            yield 'data: {"id": "chatcmpl-test", "object": "chat.completion.chunk", "choices": [{"delta": {"content": " world"}, "index": 0}]}\n\n'
            yield "data: [DONE]\n\n"

        return StreamingResponse(generate(), media_type="text/event-stream")

    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "model": deployment,
        "choices": [{"message": {"role": "assistant", "content": "Hello world"}, "index": 0}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }


@app.post("/openai/deployments/{deployment}/embeddings")
async def embeddings(deployment: str, request: Request) -> dict[str, Any]:
    body = await request.json()
    inputs = body.get("input", [])
    if isinstance(inputs, str):
        inputs = [inputs]

    return {
        "object": "list",
        "data": [
            {"object": "embedding", "index": i, "embedding": [0.1] * 1536}
            for i in range(len(inputs))
        ],
        "model": deployment,
        "usage": {"prompt_tokens": len(inputs) * 10, "total_tokens": len(inputs) * 10},
    }


@app.get("/openai/deployments/{deployment}/models")
@app.get("/openai/models")
async def list_models(deployment: str | None = None) -> dict[str, Any]:
    return {
        "object": "list",
        "data": [
            {"id": deployment or "gpt-4", "object": "model", "owned_by": "mock-foundry"},
        ],
    }


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
