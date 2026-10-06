"""Isolated generated PNG inspector: finite input and metadata-only stdout."""

from __future__ import annotations

import json
import resource
import sys


def main() -> int:
    try:
        resource.setrlimit(resource.RLIMIT_AS, (134217728, 134217728))
        resource.setrlimit(resource.RLIMIT_CPU, (1, 1))
        resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
        resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
    except (ValueError, OSError):
        return 2
    try:
        from foundry_router.api.google_output_png import (  # noqa: PLC0415 -- limits first
            MAX_PNG_BYTES,
            inspect_output_png,
        )

        result = inspect_output_png(sys.stdin.buffer.read(MAX_PNG_BYTES + 1))
    except ImportError:
        return 2
    except (ValueError, MemoryError, OverflowError):
        return 1
    sys.stdout.write(json.dumps(result, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
