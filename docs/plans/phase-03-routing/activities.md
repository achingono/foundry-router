# Phase 03 Activities

## Step-By-Step Activities
1. Confirm Phase 02 gates and inspect the current selection/forwarding seam in `main.py` and backend client.
2. Add backend health state machine (`ACTIVE`, `QUOTA_COOLDOWN`, `ERROR_COOLDOWN`, `DISABLED`) with concurrency-safe in-memory tracking protected by an `asyncio.Lock` keyed by backend ID; persist nothing.
3. Add failure classification helper: retryable (429, 500, 502, 503, 504, `httpx.TransportError`) vs non-retryable.
4. Implement bounded retry loop in `create_response` and `create_embeddings`:
   - Max attempts from `settings.retry_attempts`
   - Exponential backoff capped at `settings.retry_max_delay_seconds`
   - Robust `Retry-After` parsing supporting both integer seconds and HTTP-date formats, clamped between 0 and `retry_max_delay_seconds`
   - Abort retry on non-retryable response
   - No retry if streaming has yielded at least one chunk
5. Implement cooldown tracking:
   - On 429 → `QUOTA_COOLDOWN` for configurable duration
   - On 5xx/transport → `ERROR_COOLDOWN` for same duration
   - Exclude cooled-down backends from selection when healthy alternatives exist
   - Emergency fallback (`protected_emergency_fallback`) allows routing to cooled backend if it is the only candidate
6. Implement single failover:
   - On retryable failure after attempts exhausted, select next-highest-weight healthy backend
   - Re-execute the request on the alternate backend with fresh retry budget
   - Never retry the same backend again for the same request
   - When all candidate backends are in cooldown, return `503 Service Unavailable` (or `429` for quota exhaustion) with a `Retry-After` header matching the minimum remaining cooldown time among candidates
7. Update backend selection to filter by health state (exclude `QUOTA_COOLDOWN`, `ERROR_COOLDOWN`, `DISABLED` unless emergency fallback).
8. Add unit and integration coverage for:
   - 429 triggers quota cooldown and failover
   - Transient 5xx triggers error cooldown and failover
   - Retry exhaustion without failover when only one backend
   - A-to-B failover on first attempt failure
   - All backends in cooldown returns 503/429 with correct `Retry-After` header matching minimum remaining time
   - Robust `Retry-After` parsing (integer and HTTP-date)
   - Concurrency safety across async tasks modifying health/cooldown state
   - Streaming: failure before first chunk retries/fails over; failure after first chunk emits SSE error only
   - Client credentials never forwarded; backend credential isolated per attempt
9. Update implementation-status documentation and record verification evidence.

## Review Focus
- Retry and cooldown logic uses only configuration knobs from Phase 01; no new configuration surface.
- Backend client remains unchanged except for passing correlation ID; all routing policy stays in `main.py`.
- State mutations are thread/async safe via `asyncio.Lock`.
- Streaming SSE boundaries preserved; no buffering or retry after meaningful output.
- Upstream credentials and client secrets never logged or mixed across backends.
- Cooldown state is per-backend, not per-model; a backend in cooldown for one model is cooled for all models using it.
- Emergency fallback is opt-in and documented; default is to return error with min remaining cooldown when all backends cooled.
- Test coverage for all failure classification, retry, cooldown, failover, concurrency, and streaming edge cases.