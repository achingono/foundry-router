# Phase 08 Exit Criteria

## Gate Checklist
- [x] F1: Reservation/finalization identity is server-owned and unique per request; a regression test proves two concurrent requests with an identical client `x-request-id` reserve and finalize independently.
- [x] F1: Client correlation ID is still validated, echoed in `x-request-id`, bound to logs, and forwarded upstream unchanged.
- [x] F2: Oversized request bodies are rejected with `413` before JSON parsing, for both `Content-Length` and no-`Content-Length` cases; `max_request_body_bytes` is validated and documented.
- [x] F2: Token-estimation recursion/character walk is bounded and fails closed on over-limit input.
- [x] F3: Incomplete per-backend credit config and per-model pricing are rejected at config load, or clearly reported by `/health/ready`; the chosen approach is recorded and the message names only IDs (no secrets). (Implemented as a `/health/ready` check; see risk register R3.)
- [x] F4: Orphaned reservations older than `reservation_max_age_seconds` are reclaimed and their inflight amounts released; a fresh reservation is untouched; mechanism is bounded (no unbounded background work); reservation count/age is visible via `/admin/status`.
- [x] F5: `parse_retry_after` returns `None` (no exception) for non-ASCII digit headers.
- [x] F6: Per-request `sync_from_settings` is removed from the routing hot path without behaviour regressions in routing, `/admin/status`, or `/metrics`. (Retained instead of removed, with a settings-identity fast path; see risk register R5.)
- [x] F7: Streaming usage extraction is pre-filtered with identical charged-cost results for usage-bearing terminal events; SSE boundaries unchanged.
- [x] F8: Auth comparisons evaluate all configured keys without early return; valid keys at any position authenticate.
- [x] Streaming/SSE event boundaries and the no-retry-after-output rule remain intact.
- [x] Full suite passes via `.venv/bin/python -m pytest`; coverage for implemented code is >= 80%. (187 passed, 90.80% coverage.)
- [x] Ruff, formatter, and Mypy pass; SonarQube scan and deep-review prompt (where present) have no unresolved `Blocker`/`Critical`/`Major` findings. (Scan script and deep-review prompt are not present in this repository.)
- [ ] Docker build succeeds where applicable. (Docker CLI unavailable in this environment; not verified.)
- [x] Requirements traceability, security, observability, and configuration docs updated with verified behaviour only; relative links validated.
- [x] Final diff reviewed for unsupported present-tense claims, secrets, or hard-coded identifiers.

## Approval Table

| Role | Name | Status | Notes |
| --- | --- | --- | --- |
| Owner | | Pending | |
| Reviewer | | Pending | |
| Approver | | Pending | |
