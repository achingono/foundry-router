# Phase 04 Hardening Exit Criteria

## Criteria Checklist

- [ ] `MAX_SSE_EVENT_BUFFER_BYTES` limit enforced during streaming response consumption.
- [ ] In-flight credit reservations guaranteed to release under all cancellation and secondary failover exception paths.
- [ ] Non-2xx responses strictly release credit reservations without deducting estimated cost.
- [ ] Terminal SSE usage parsing safely extracts token counts when present and falls back gracefully when absent.
- [ ] Module coverage for `src/foundry_router/credit.py` remains >= 90% and total coverage >= 85%.
- [ ] Zero Ruff lint/format errors and zero Mypy type check errors.
