# Phase 08 Exit Criteria

## Gate Checklist
- [ ] F1: Reservation/finalization identity is server-owned and unique per request; a regression test proves two concurrent requests with an identical client `x-request-id` reserve and finalize independently.
- [ ] F1: Client correlation ID is still validated, echoed in `x-request-id`, bound to logs, and forwarded upstream unchanged.
- [ ] F2: Oversized request bodies are rejected with `413` before JSON parsing, for both `Content-Length` and no-`Content-Length` cases; `max_request_body_bytes` is validated and documented.
- [ ] F2: Token-estimation recursion/character walk is bounded and fails closed on over-limit input.
- [ ] F3: Incomplete per-backend credit config and per-model pricing are rejected at config load, or clearly reported by `/health/ready`; the chosen approach is recorded and the message names only IDs (no secrets).
- [ ] F4: Orphaned reservations older than `reservation_max_age_seconds` are reclaimed and their inflight amounts released; a fresh reservation is untouched; mechanism is bounded (no unbounded background work); reservation count/age is visible via `/admin/status`.
- [ ] F5: `parse_retry_after` returns `None` (no exception) for non-ASCII digit headers.
- [ ] F6: Per-request `sync_from_settings` is removed from the routing hot path without behaviour regressions in routing, `/admin/status`, or `/metrics`.
- [ ] F7: Streaming usage extraction is pre-filtered with identical charged-cost results for usage-bearing terminal events; SSE boundaries unchanged.
- [ ] F8: Auth comparisons evaluate all configured keys without early return; valid keys at any position authenticate.
- [ ] Streaming/SSE event boundaries and the no-retry-after-output rule remain intact.
- [ ] Full suite passes via `.venv/bin/python -m pytest`; coverage for implemented code is >= 80%.
- [ ] Ruff, formatter, and Mypy pass; SonarQube scan and deep-review prompt (where present) have no unresolved `Blocker`/`Critical`/`Major` findings.
- [ ] Docker build succeeds where applicable.
- [ ] Requirements traceability, security, observability, and configuration docs updated with verified behaviour only; relative links validated.
- [ ] Final diff reviewed for unsupported present-tense claims, secrets, or hard-coded identifiers.

## Approval Table

| Role | Name | Status | Notes |
| --- | --- | --- | --- |
| Owner | | Pending | |
| Reviewer | | Pending | |
| Approver | | Pending | |
