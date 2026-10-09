"""A real loopback client must receive text before producer completion and disconnect."""

import asyncio
import sys
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/quality"))
from google_loopback import serve_loopback


@pytest.mark.asyncio
async def test_loopback_incremental_disconnect_closes_producer_without_reaper():
    app = FastAPI()
    released = asyncio.Event()
    finished = False

    @app.get("/stream")
    async def stream():
        async def chunks():
            nonlocal finished
            try:
                yield b"data: first\n\n"
                await asyncio.sleep(10)
                finished = True
                yield b"data: final\n\n"
            finally:
                released.set()

        return StreamingResponse(chunks(), media_type="text/event-stream")

    async with serve_loopback(app) as origin:
        async with httpx.AsyncClient(trust_env=False, timeout=2) as client:
            async with client.stream("GET", origin + "/stream") as response:
                assert await response.aiter_bytes().__anext__() == b"data: first\n\n"
                assert not finished
            async with asyncio.timeout(1):
                await released.wait()
    with pytest.raises(httpx.ConnectError):
        async with httpx.AsyncClient(trust_env=False, timeout=0.2) as client:
            await client.get(origin + "/stream")


@pytest.mark.asyncio
async def test_cancelled_owner_joins_listener_shutdown():
    started = asyncio.Event()
    origins = []

    async def owner():
        async with serve_loopback(FastAPI()) as origin:
            origins.append(origin)
            started.set()
            await asyncio.sleep(10)

    task = asyncio.create_task(owner())
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    with pytest.raises(httpx.ConnectError):
        async with httpx.AsyncClient(trust_env=False, timeout=0.2) as client:
            await client.get(origins[0])
