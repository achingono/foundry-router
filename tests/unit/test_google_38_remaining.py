"""Unused slots never reopen pinned, consumed 3.8 attempts."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/quality"))
import google_38_remaining as remaining


def test_combined_budget_and_consumed_slot_refusal(tmp_path, monkeypatch):
    prior = [
        {
            "attempts": {
                "g38-native-project-1": {"physical_attempts": [{}]},
                "g38-nonstream-project-1": {"physical_attempts": [{}]},
            }
        },
        {"attempts": {"g38-nonstream-project-1": {"physical_attempts": [{}]}}},
    ]
    pins = {}
    for index, data in enumerate(prior):
        name = f"prior-{index}.json"
        raw = json.dumps(data).encode()
        (tmp_path / name).write_bytes(raw)
        pins[name] = hashlib.sha256(raw).hexdigest()
    monkeypatch.setattr(remaining, "PINS", pins)
    monkeypatch.setattr(remaining.diagnostic, "DIRECTORY", tmp_path)
    ledger = remaining.Ledger(tmp_path / "new.json", b"historical")
    ledger.reserve("project-1", "g38-nonstream-project-1", 1088)
    with pytest.raises(ValueError):
        ledger.start_physical("g38-nonstream-project-1")
    ledger = remaining.Ledger(tmp_path / "another.json", b"historical")
    ledger.reserve("project-1", "g38-stream-project-1", 1088)
    for _ in range(3):
        ledger.start_physical("g38-stream-project-1")
    with pytest.raises(ValueError):
        ledger.start_physical("g38-stream-project-1")
    (tmp_path / "prior-0.json").write_text("{}")
    with pytest.raises(ValueError):
        remaining.originals()
