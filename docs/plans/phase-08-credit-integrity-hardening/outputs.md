# Phase 08 Outputs

## Mandatory Outputs

| Output | Description | Format |
| --- | --- | --- |
| Server-owned reservation identity | `main.py` generates a unique internal request key; routes thread it into routing/credit/streaming instead of the client `x-request-id` | Source change + tests |
| Bounded request intake | `request_body` rejects oversized bodies (413) before parsing; new `max_request_body_bytes` setting; bounded token-estimation recursion | Source change + tests |
| Config completeness invariant | Config-load (or readiness) enforces complete per-backend credit config and per-model pricing with a secret-free message/check | Source change + tests |
| Reservation lifecycle safety | `_Reservation` age tracking, bounded reaper, and `reservation_max_age_seconds` setting; admin visibility of reservation count/age | Source change + tests |
| Retry-After hardening | `parse_retry_after` never raises on non-ASCII digit headers | Source change + test |
| Hot-path sync removal | Per-request `sync_from_settings` removed from routing without behaviour regressions | Source change + tests |
| Cheaper stream usage extraction | Pre-filtered SSE usage parsing with unchanged charged-cost semantics | Source change + test |
| Constant-work auth comparison | Auth loops compare all keys without early return | Source change + test |
| Updated documentation | Traceability, security, observability, and configuration docs reflect verified behaviour | Markdown |
| Verification evidence | Test, coverage, lint, type, scan, and build results recorded | Evidence log |

## Optional Outputs
- A short ADR note if the F3 invariant materially changes configuration requirements.
- Additional admin/status diagnostics for oldest-reservation age if inexpensive.

## Output Quality Checklist
- [ ] All mandatory outputs produced
- [ ] All outputs reviewed before gate
- [ ] Evidence log updated with output references
- [ ] Documentation uses only `Implemented`/`Partially implemented`/`Planned`/`Design target` labels accurately
