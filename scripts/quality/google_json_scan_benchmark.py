"""Finite scanner measurements on original strict JSON; synthetic content only."""

import json
import resource
import time

from foundry_router.api.adapters.google_schema import load_bounded_json

cases = {
    "plain": "x" * 2000000,
    "quotes": '"' * 1000000,
    "backslashes": "\\" * 1000000,
    "odd_backslashes_quote": "\\" * 999999 + '"',
    "unicode_escaped_structural": ('\\"😀[]{}') * 100000,
}
rows = []
for name, value in cases.items():
    wire = json.dumps(value, ensure_ascii=False)
    started = time.monotonic()
    parsed = load_bounded_json(wire, max_bytes=2097152)
    rows.append(
        {
            "case": name,
            "wire_bytes": len(wire.encode()),
            "parse_ms": (time.monotonic() - started) * 1000,
            "lossless": parsed == value,
        }
    )
    del parsed, wire
print(
    json.dumps(
        {
            "synthetic_only": True,
            "scope": "strict scanner microbenchmark, no HTTP evidence",
            "rows": rows,
            "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        },
        sort_keys=True,
    )
)
