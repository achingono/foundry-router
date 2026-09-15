# Phase 04 Hardening Exit Criteria

> **Status:** All criteria below are verified complete per `evidence.md` (coverage >= 85%, `credit.py` cancellation/SSE/non-2xx test coverage, lint/type checks clean).

## Criteria Checklist

- [x] `MAX_SSE_EVENT_BUFFER_BYTES` limit enforced during streaming response consumption.
- [x] In-flight credit reservations guaranteed to release under all cancellation and secondary failover exception paths.
- [x] Non-2xx responses strictly release credit reservations without deducting estimated cost.
- [x] Terminal SSE usage parsing safely extracts token counts when present and falls back gracefully when absent.
- [x] Module coverage for `src/foundry_router/credit.py` remains >= 90% and total coverage >= 85%.
- [x] Zero Ruff lint/format errors and zero Mypy type check errors.
