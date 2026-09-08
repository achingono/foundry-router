# Phase 08 Activities

Implement the findings in the order below. Each finding is independent enough to land as its own commit with its own tests, but F1, F3, and F4 all touch `credit.py`, so sequence them as listed to minimise churn. Do not weaken the streaming/SSE contract or the "never retry or fail over after meaningful streaming output begins" rule while editing forwarding.

## F1 (Critical) — Decouple client `x-request-id` from the reservation key
1. In `src/foundry_router/main.py` `add_correlation_id`, keep accepting and echoing the validated client `x-request-id` as the **logging correlation ID** only. Additionally generate a server-owned, always-unique request key and store it separately, for example `request.state.request_key = str(uuid.uuid4())`. Never derive `request_key` from any client-supplied value.
2. In `src/foundry_router/api/routes/openai.py`, pass `request.state.request_key` (not `request.state.correlation_id`) as the `request_id` argument into `execute_with_single_failover` and into `forward_streaming_with_retries`. Continue using `correlation_id` for `forward_headers`/`x-request-id` echo and log binding.
3. Confirm the value threaded into `select_candidate_backend` → `try_assign_reservation` → `finalize_request` and into `stream_response(request_id=...)` is the server-owned key end to end.
4. Leave `forward_headers` behaviour (forwarding the client correlation ID upstream as `x-request-id`) unchanged; only the reservation/finalization identity changes.
5. Add a regression test proving two concurrent requests that send an identical client `x-request-id` each create a distinct reservation and each finalize independently (no piggybacking, no lost charge).

## F2 (Major) — Bound request intake
6. In `src/foundry_router/api/common.py` `request_body`, enforce a maximum body size before parsing. Reject when `Content-Length` exceeds a configured limit, and when `Content-Length` is absent, read with a hard cap and reject overflow. Return `413` with the existing `api_error` shape and an `invalid_request`-style type.
7. Add a `max_request_body_bytes` setting to `src/foundry_router/config/__init__.py` with a safe default and bounded validation, wired through the existing settings pattern (env alias, finite/positive check).
8. In `src/foundry_router/credit.py`, bound `_walk_text_chars` recursion depth (and/or total character count) so deeply nested JSON cannot cause excessive recursion; treat over-limit input as an estimation failure (return the existing sentinel that fails closed).
9. Add tests for oversized `Content-Length`, oversized streamed body without `Content-Length`, and deeply nested estimation input.

## F3 (Major) — Fail loudly on incomplete credit/pricing config
10. Decide and document the invariant: every backend referenced by any model pool MUST have complete credit configuration (allowance, initial estimated remaining, and cycle start day), and every configured model MUST have a pricing entry.
11. Implement the invariant at config load in `src/foundry_router/config/__init__.py` `parse_json_fields` (preferred, fail-fast) with an explicit, redacted error message naming the offending backend or model. If a hard failure is judged too strict for partial local testing, instead surface the gap in `src/foundry_router/api/routes/health.py` `/health/ready` as a new named check; choose one approach and record the decision in the risk register and traceability.
12. Ensure the error/check text does not leak secrets and names only IDs.
13. Add tests: backend in a model pool with missing credit config is rejected/flagged; model without pricing is rejected/flagged; fully configured setup passes.

## F4 (Major) — Reservation age tracking and reaper
14. In `src/foundry_router/credit.py`, add a monotonic creation timestamp to `_Reservation`. Add a bounded sweep that releases reservations older than a configurable maximum age (request timeout plus margin) with `charge_reserved=False`. Implement the sweep lazily inside `assess`/`try_assign_reservation` (under the existing lock) and/or as a small periodic task; do not add unbounded background work.
15. Add a `reservation_max_age_seconds` setting to `config` with bounded validation and a safe default aligned to the backend client timeout.
16. Surface active reservation count and, if cheap, oldest-reservation age per backend in `src/foundry_router/api/routes/admin.py` `/admin/status` for observability. Reuse the existing `live_snapshot` path.
17. Add tests: an orphaned reservation older than the max age is reclaimed and its inflight amount is released; a fresh reservation is untouched.

## F5 (Suggestion) — Harden `parse_retry_after`
18. In `src/foundry_router/forwarding/__init__.py` `parse_retry_after`, require ASCII digits (for example `value.isascii() and value.isdigit()`) before `float(value)`, or wrap the numeric parse so a non-parseable value returns `None` instead of raising. Add a test with a non-ASCII digit header asserting `None` and no exception.

## F6 (Suggestion) — Remove redundant hot-path sync
19. Stop calling `credit_store.sync_from_settings` on every request in `src/foundry_router/routing/__init__.py` `select_candidate_backend`. Rely on the startup sync in `lifespan` and the reconciliation path. If a first-call guarantee is needed, make `sync_from_settings` a cheap no-op after initialization. Keep `/admin/status` and `/metrics` behaviour correct.
20. Add or adjust tests so routing does not depend on a per-request sync side effect.

## F7 (Suggestion) — Cheaper streaming usage extraction
21. In `src/foundry_router/forwarding/__init__.py` `process_event_payload`, add a cheap pre-filter (for example only attempt `json.loads` when the raw event contains `b"usage"`), preserving exact charged-cost behaviour for the terminal usage event. Keep SSE event boundaries intact. Add a test asserting cost is still extracted from a usage-bearing terminal event and that non-usage deltas are skipped.

## F8 (Suggestion) — Constant-work auth comparison
22. In `src/foundry_router/auth/__init__.py`, replace the early-return match loop in both `verify_client_auth` and `verify_admin_auth` with a form that compares against all configured keys without short-circuiting (accumulate a match flag), keeping `hmac.compare_digest` per comparison. Preserve existing error messages and header behaviour. Add a test that a valid key at any position authenticates.

## Documentation and verification (all findings)
23. Update `docs/decisions/requirements-traceability.md` to reflect the corrected credit-identity, intake-bounding, config-validation, and reservation-lifecycle behaviour.
24. Update `docs/configuration/security.md` (request-size limits, correlation-vs-reservation identity) and `docs/operations/observability.md` (reservation age/count fields) with verified behaviour only.
25. If the F3 invariant changes configuration requirements, update `docs/configuration/index.md` and the getting-started example accordingly.
26. Record all evidence in [Evidence](evidence.md).
27. Run focused tests per finding, then the full suite via `.venv/bin/python -m pytest`, then coverage (maintain >= 80% for implemented code), Ruff, formatter, and Mypy. Run `scripts/quality/sonarqube-scan.sh` and the deep-review prompt if present and address `Blocker`/`Critical`/`Major` findings. Run a Docker build where applicable.

## Review Focus
- No client-supplied value can influence the reservation/finalization identity; duplicate client IDs cannot cause under-reservation or lost charges.
- Request intake is bounded and rejects oversized bodies before allocation; token estimation cannot be driven into pathological recursion.
- Misconfigured credit/pricing fails fast with a clear, secret-free message (or is clearly reported by readiness), never as a silent permanent 503.
- Inflight credit cannot leak: orphaned reservations are reclaimed and the mechanism is bounded and observable.
- Streaming/SSE boundaries and the no-retry-after-output rule are unchanged.
- No secrets, prompts, or outputs appear in new logs, errors, or docs.
