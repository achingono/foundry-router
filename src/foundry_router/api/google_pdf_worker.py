"""Isolated bounded PDF inspector; stdout carries only finite metadata."""

from __future__ import annotations

import json
import logging
import resource
import sys


def main() -> int:
    logging.getLogger().handlers.clear()
    try:
        resource.setrlimit(resource.RLIMIT_CPU, (2, 2))
        resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
        resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
    except (ValueError, OSError):
        return 2
    try:
        from foundry_router.api.google_pdf_syntax import (  # noqa: PLC0415 -- limits first
            inspect_pdf,
        )

        data = sys.stdin.buffer.read(65537)
        pages = inspect_pdf(data)
    except ImportError:
        return 2
    except (ValueError, TypeError, KeyError, MemoryError, RecursionError):
        return 1
    sys.stdout.write(json.dumps({"pages": pages, "bytes": len(data)}, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
