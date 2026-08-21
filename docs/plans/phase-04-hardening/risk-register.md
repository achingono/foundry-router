# Phase 04 Hardening Risk Register

## Risk Assessment

| Risk ID | Description | Impact | Likelihood | Mitigation |
|---|---|---|---|---|
| R-P04H-01 | Unbounded SSE chunk accumulation causes memory leak under malformed stream | High | Low | Enforce explicit `MAX_SSE_EVENT_BUFFER_BYTES` limit and flush on overflow. |
| R-P04H-02 | Stream usage extraction parses invalid JSON and halts stream generator | High | Low | Wrap JSON decoding in strict `try...except` and pass raw bytes unchanged to client. |
| R-P04H-03 | Concurrent client disconnects leave orphaned credit reservations | High | Low | Enclose entire execution lifecycle in top-level `try...finally` block. |
