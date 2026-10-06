"""Two sequential fresh synthetic interpreters; emit only redacted replay/cleanup facts."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from google_signed_process import BODY, MAX_PIPE_BYTES

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = Path(__file__).with_name("google_signed_process.py")
MAX_ERROR_BYTES = 4096


async def child(body, changed_key=False):
    wire = json.dumps({"body": body, "changed_key": changed_key}).encode()
    if len(wire) > MAX_PIPE_BYTES:
        raise ValueError("Synthetic input boundary exceeded")
    env = {
        "PATH": os.defpath,
        "PYTHONPATH": str(ROOT / "src"),
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        str(SCRIPT),
        cwd=ROOT,
        env=env,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        limit=MAX_ERROR_BYTES,
    )

    async def bounded_read(reader, limit):
        data = await reader.read(limit + 1)
        # read(n) may return short chunks; require EOF before accepting the channel.
        while len(data) <= limit:
            chunk = await reader.read(limit + 1 - len(data))
            if not chunk:
                return data
            data += chunk
        raise ValueError("Synthetic output boundary exceeded")

    readers = []

    async def communicate():
        process.stdin.write(wire)
        await process.stdin.drain()
        process.stdin.close()
        readers.extend(
            [
                asyncio.create_task(bounded_read(process.stdout, MAX_PIPE_BYTES)),
                asyncio.create_task(bounded_read(process.stderr, MAX_ERROR_BYTES)),
            ]
        )
        stdout, stderr = await asyncio.gather(*readers)
        await process.wait()
        if process.returncode != 0 or stderr:
            raise ValueError("Synthetic interpreter failed")
        result = json.loads(stdout)
        if result["summary"]["pid"] != process.pid:
            raise ValueError("Synthetic interpreter identity mismatch")
        return result

    work = asyncio.create_task(communicate())
    try:
        async with asyncio.timeout(15):
            return await work
    finally:

        async def cleanup():
            if not work.done():
                work.cancel()
            for reader in readers:
                reader.cancel()
            await asyncio.gather(work, *readers, return_exceptions=True)
            if process.returncode is None:
                process.kill()

            async def discard(reader):
                while await reader.read(MAX_ERROR_BYTES):
                    pass

            # Drain discarded bytes after kill so paused subprocess pipe transports
            # cannot prevent process.wait() from observing a fully closed child.
            await asyncio.gather(discard(process.stdout), discard(process.stderr))
            await process.wait()

        cleanup_task = asyncio.create_task(cleanup())
        while not cleanup_task.done():
            try:
                await asyncio.shield(cleanup_task)
            except asyncio.CancelledError:
                continue
        cleanup_task.result()


async def verify(changed_key=False):
    first = await child(BODY)
    replay = {
        **BODY,
        "input": [
            *BODY["input"],
            *first["private_response"]["output"],
            {"role": "user", "content": "synthetic-next"},
        ],
    }
    # First interpreter was awaited and reaped; only then is the second launched.
    second = await child(replay, changed_key)
    a, b = first["summary"], second["summary"]
    assert a["pid"] != b["pid"]
    assert a["dispatches"] == 1 and b["dispatches"] == (0 if changed_key else 1)
    assert b["http_status"] == (422 if changed_key else 200)
    assert b["exact_native_replay"] is not changed_key
    for facts in (a, b):
        assert facts["credit_and_quota_cleanup"] and facts["signed_capacity_released"]
        summary = json.dumps(facts)
        for marker in (
            "synthetic-question",
            "synthetic-key",
            "synthetic-answer",
            "c3ludGhldGljLXNpZw==",
            "fixture.",
        ):
            assert marker not in summary
    return {
        "synthetic_only": True,
        "python_version": sys.version.split()[0],
        "scope": "sequential fresh interpreter ASGI/SDK replay; no live or TCP evidence",
        "first_exited_before_second_started": True,
        "distinct_processes": True,
        "changed_key": changed_key,
        "first": a,
        "second": b,
        "passed": True,
    }


async def main():
    try:
        result = [await verify(), await verify(changed_key=True)]
        print(json.dumps(result, sort_keys=True))
        return 0  # noqa: TRY300
    except (OSError, ValueError, TypeError, KeyError, AssertionError, TimeoutError):
        print(json.dumps({"status": "synthetic_restart_failed"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
