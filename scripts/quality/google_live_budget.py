"""Durable redacted session budgets for isolated Google checks; no credentials."""

from __future__ import annotations

import fcntl
import json
import os
import re
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from foundry_router.api.adapters.google_schema import load_bounded_json

REQUEST_LIMIT = 20
TOKEN_LIMIT = 20000
MAX_LEDGER_BYTES = 65536

SESSION = "google-tools-multimodal-2026-10-06"


@contextmanager
def locked(path: Path):
    with path.with_suffix(path.suffix + ".lock").open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def write_atomic(path: Path, data: dict[str, Any]) -> None:
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=".google-budget-")
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(data, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        Path(name).replace(path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        Path(name).unlink(missing_ok=True)


class BudgetLedger:
    def __init__(self, path: Path):
        self.path = path
        with locked(path):
            if not path.exists():
                write_atomic(
                    path,
                    {
                        "session": SESSION,
                        "projects": {
                            f"project-{i}": {
                                "requests": 1,
                                "tokens": 0,
                                "halted": False,
                                "cases": {},
                            }
                            for i in range(1, 6)
                        },
                    },
                )
            self._read()

    def _read(self) -> dict[str, Any]:
        if self.path.stat().st_size > MAX_LEDGER_BYTES:
            raise ValueError("Invalid budget ledger")
        data = load_bounded_json(self.path.read_bytes().decode(), max_bytes=MAX_LEDGER_BYTES)
        if (
            not isinstance(data, dict)
            or not isinstance(data.get("projects"), dict)
            or data.get("session") != SESSION
            or set(data.get("projects", {})) != {f"project-{i}" for i in range(1, 6)}
        ):
            raise ValueError("Invalid budget ledger")
        for project in data["projects"].values():
            if (
                not isinstance(project, dict)
                or set(project) != {"requests", "tokens", "halted", "cases"}
                or type(project["requests"]) is not int
                or not 1 <= project["requests"] <= REQUEST_LIMIT
                or type(project["tokens"]) is not int
                or project["tokens"] < 0
                or type(project["halted"]) is not bool
                or not isinstance(project["cases"], dict)
                or (project["tokens"] > TOKEN_LIMIT and not project["halted"])
            ):
                raise ValueError("Invalid budget ledger")
            if project["requests"] != 1 + len(project["cases"]):
                raise ValueError("Invalid budget ledger")
            accounted = 0
            overrun = False
            for label, case in project["cases"].items():
                if (
                    not isinstance(label, str)
                    or re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", label) is None
                    or not isinstance(case, dict)
                    or set(case) != {"reserved_tokens", "actual_tokens"}
                    or type(case["reserved_tokens"]) is not int
                    or not 1 <= case["reserved_tokens"] <= TOKEN_LIMIT
                    or (
                        case["actual_tokens"] is not None
                        and (type(case["actual_tokens"]) is not int or case["actual_tokens"] < 0)
                    )
                ):
                    raise ValueError("Invalid budget ledger")
                accounted += max(case["reserved_tokens"], case["actual_tokens"] or 0)
                overrun |= (case["actual_tokens"] or 0) > case["reserved_tokens"]
            if accounted != project["tokens"] or (overrun and not project["halted"]):
                raise ValueError("Invalid budget ledger")
        return data

    def reserve(self, project_label: str, case_id: str, tokens: int) -> None:
        if (
            not isinstance(case_id, str)
            or re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", case_id) is None
            or type(tokens) is not int
            or not 1 <= tokens <= TOKEN_LIMIT
        ):
            raise ValueError("Invalid token reservation")
        with locked(self.path):
            data = self._read()
            project = data["projects"][project_label]
            if (
                project["halted"]
                or case_id in project["cases"]
                or project["requests"] >= REQUEST_LIMIT
                or project["tokens"] + tokens > TOKEN_LIMIT
            ):
                raise ValueError("Project budget unavailable")
            project["requests"] += 1
            project["tokens"] += tokens
            project["cases"][case_id] = {"reserved_tokens": tokens, "actual_tokens": None}
            write_atomic(self.path, data)

    def record_usage(self, project_label: str, case_id: str, tokens: int) -> None:
        if type(tokens) is not int or tokens < 0:
            raise ValueError("Invalid actual usage")
        with locked(self.path):
            data = self._read()
            project = data["projects"][project_label]
            case = project["cases"][case_id]
            if case["actual_tokens"] is not None:
                raise ValueError("Usage already recorded")
            case["actual_tokens"] = tokens
            # Never refund reservations: failed, abandoned and rerun cases remain charged.
            extra = max(0, tokens - case["reserved_tokens"])
            project["tokens"] += extra
            if extra:
                project["halted"] = True
            write_atomic(self.path, data)
