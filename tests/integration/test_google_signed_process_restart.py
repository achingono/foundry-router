"""Fresh interpreter signed replay with bounded private synthetic pipes."""

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "signed_restart", ROOT / "scripts/quality/google_signed_restart.py"
)


@pytest.mark.parametrize("changed_key", [False, True])
async def test_signed_carrier_replays_after_previous_interpreter_exit(monkeypatch, changed_key):
    monkeypatch.syspath_prepend(str(ROOT / "scripts/quality"))
    assert SPEC is not None and SPEC.loader is not None
    module = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(module)
    facts = await module.verify(changed_key)
    assert facts["passed"] and facts["distinct_processes"]
    assert facts["first_exited_before_second_started"]
    assert facts["python_version"] == sys.version.split()[0]


def load_harness(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts/quality"))
    assert SPEC is not None and SPEC.loader is not None
    module = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(module)
    return module


@pytest.mark.parametrize("channel", ["stdout", "stderr"])
async def test_restart_private_pipe_overflow_kills_and_reaps(monkeypatch, tmp_path, channel):
    import asyncio

    module = load_harness(monkeypatch)
    script = tmp_path / "overflow.py"
    script.write_text(
        "import sys, time\n"
        f"sys.{channel}.buffer.write(b'x' * 1048576)\n"
        f"sys.{channel}.buffer.flush()\n"
        "time.sleep(60)\n"
    )
    monkeypatch.setattr(module, "SCRIPT", script)
    original = asyncio.create_subprocess_exec
    children = []

    async def spawn(*args, **kwargs):
        process = await original(*args, **kwargs)
        children.append(process)
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    with pytest.raises(ValueError, match="boundary exceeded"):
        await asyncio.wait_for(module.child(module.BODY), 3)
    assert len(children) == 1 and children[0].returncode is not None


async def test_restart_parent_cancellation_reaps_child(monkeypatch, tmp_path):
    import asyncio

    module = load_harness(monkeypatch)
    script = tmp_path / "waiting.py"
    script.write_text("import time\ntime.sleep(60)\n")
    monkeypatch.setattr(module, "SCRIPT", script)
    original = asyncio.create_subprocess_exec
    children = []
    started = asyncio.Event()

    async def spawn(*args, **kwargs):
        process = await original(*args, **kwargs)
        children.append(process)
        started.set()
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    task = asyncio.create_task(module.child(module.BODY))
    await asyncio.wait_for(started.wait(), 1)
    await asyncio.sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, 3)
    assert len(children) == 1 and children[0].returncode is not None
