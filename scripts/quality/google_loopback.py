"""Owned localhost HTTP listener for actual incremental verification clients."""

from __future__ import annotations

import asyncio
import socket
from contextlib import asynccontextmanager, nullcontext

import uvicorn

STARTUP_SECONDS = 2
SHUTDOWN_SECONDS = 2
POLL_SECONDS = 0.01


class LoopbackServer(uvicorn.Server):
    def capture_signals(self):
        return nullcontext()


async def stop_server(server, task, listener):
    try:
        server.should_exit = True
        done, _ = await asyncio.wait({task}, timeout=SHUTDOWN_SECONDS)
        if not done:
            server.force_exit = True
            task.cancel()
            done, _ = await asyncio.wait({task}, timeout=SHUTDOWN_SECONDS)
            if not done:
                _unfinished_servers.add(task)
                task.add_done_callback(_consume_server)
            elif not task.cancelled():
                task.exception()
            raise RuntimeError("Verification server shutdown unavailable") from None
        task.result()
    finally:
        listener.close()


_unfinished_servers = set()


def _consume_server(task):
    _unfinished_servers.discard(task)
    if not task.cancelled():
        task.exception()


@asynccontextmanager
async def serve_loopback(app):
    if _unfinished_servers:
        raise RuntimeError("Previous verification server shutdown incomplete")
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    task = None
    try:
        listener.bind(("127.0.0.1", 0))
        listener.listen(16)
        listener.setblocking(False)
        port = listener.getsockname()[1]
        server = LoopbackServer(
            uvicorn.Config(
                app,
                host="127.0.0.1",
                port=port,
                access_log=False,
                log_config=None,
                lifespan="off",
                timeout_graceful_shutdown=1,
                ws="none",
            )
        )
        task = asyncio.create_task(server.serve(sockets=[listener]))
        async with asyncio.timeout(STARTUP_SECONDS):
            while not server.started:
                if task.done():
                    task.result()
                    raise RuntimeError("Verification server startup unavailable")
                await asyncio.sleep(POLL_SECONDS)
        yield f"http://127.0.0.1:{port}"
    finally:
        if task is None:
            listener.close()
        else:
            cleanup = asyncio.create_task(stop_server(server, task, listener))
            cancelled = False
            while not cleanup.done():
                try:
                    await asyncio.shield(cleanup)
                except asyncio.CancelledError:
                    cancelled = True
            cleanup.result()
            if cancelled:
                raise asyncio.CancelledError
