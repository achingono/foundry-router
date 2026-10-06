# Deep Review — Current Uncommitted Changes (2026-10-06)

Scope: `git diff` (~2,455 insertions across 40 tracked files) + ~7,332 lines new Google surface (`api/google_*.py`, `api/adapters/google_*.py`, `config/google_*.py`). Per `.agents/prompts/deep-review.prompt.md`: no style/smells/coverage/CVE focus.

Status note per `AGENTS.md`: sealed native (`bound_history_required`), generated image, generated audio are **Planned / Design target** — `config/__init__.py:527,719-726` unconditionally raises `Signed native runtime integration is not yet available` / `runtime is unavailable pending integration gates`. All findings below about those paths are about **Implemented-but-prod-dead** code, not deployed behavior.

## Critical

* **File/Module:** `src/foundry_router/api/adapters/google_signed.py:64-91`, `src/foundry_router/api/google_continuation.py:63-67`, `src/foundry_router/api/google_history.py:111-143`
* **The Issue:** Full-strip downgrade. `check_request` only enforces sealing if `carrier_tokens(body)` non-empty. If attacker deletes every per-item `foundry_provider_state` (keeps top-level version), `prepared is None`, `_ordinary_body()` strips and delegates to unsigned `GoogleNativeAdapter`, which permits arbitrary `assistant`/`function_call` history. `thinkingBudget` is still injected even on this unsigned fallback.
* **Why Static Analysis Missed It:** Each file looks fail-closed (`raise ProviderStateError`); invariant “sealed pool = zero unsigned assistant turns” spans 3 files.
* **Impact:** Signature bypass; forged history executed/billed with thinking enabled.
* **Recommended Fix:** When `continuation_policy==sealed_native` and `prepared is None`, require zero `assistant`/`function_call` items, or set `thinkingBudget=0` for fresh turns. Regression test: sealed history minus carriers → 422.

* **File/Module:** `src/foundry_router/forwarding/__init__.py:521-544,602` vs `routing/__init__.py:1121-1162`
* **The Issue:** Azure terminal retryable (5xx / post-send `TransportError`) returns `retryable_failure=True` with no `settlement_cost_usd`/`force_charge`. Routing then refunds (`charge_reserved=False`) while retaining quota. Google path for same ambiguity force-charges fallback estimate.
* **Why Static Analysis Missed It:** Cross-module economics; `retryable=True` looks safe, Azure vs Google settlement tables only comparable via docstring.
* **Impact:** Two upstream executions, one charge. Violates “5xx never proves non-generation”.
* **Recommended Fix:** Return `force_charge=True` + fallback estimate on Azure terminal retryable after dispatch; split pre-connect vs post-send `TransportError`.

* **File/Module:** `src/foundry_router/credit.py:728-775` (`InMemoryCreditStore.sync_from_settings`)
* **The Issue:** `if settings is self._last_synced_settings and aliases==... and groups==...: return` skips allowance reconciliation. Same-identity + mutated amounts (mutable Pydantic, `lru_cache` singleton) keeps stale posture. Also pins full `Settings` including `google_state_keys` secret material.
* **Why Static Analysis Missed It:** Looks like pure memoization; requires knowing allowance ≠ membership.
* **Impact:** Over-admission (overspend) or under-admission (spurious 503) until restart; secret retention past rotation.
* **Recommended Fix:** Compare allowance maps too or always reconcile amounts; store revision int, not `Settings` object; ensure key rotation calls `reset()`.

* **File/Module:** `src/foundry_router/api/google_work.py:13,76-98`, `src/foundry_router/api/common.py:76-87`, `src/foundry_router/api/routes/openai.py:105-112`
* **The Issue:** One global `threading.BoundedSemaphore(2)` shared by sealed crypto (`with lease`) and generic `offload_json` parse (`owned=True`). `offload_json` enabled if *any* pool is `bound_history_required`, not the target model — all `/responses` traffic (including Azure/compat) contends for 2 slots.
* **Why Static Analysis Missed It:** Acquire/release balanced; contention only visible correlating two call-sites.
* **Impact:** Availability DoS; cheap compat flood starves sealed intake; 2×2MB parses block crypto.
* **Recommended Fix:** Separate pools (crypto vs JSON executor/`to_thread` without slot); scope `offload_json` to resolved model only.

* **File/Module:** `src/foundry_router/api/routes/openai.py:145,197-203`, `src/foundry_router/api/google_output_work.py:18,48-115`, `src/foundry_router/api/google_output_delivery.py:26-56`
* **The Issue:** Process-global inspection semaphore (2 slots) held across upstream RTT + downstream delivery (`bind_delivery_deadline` → `owner.transfer` retains until ASGI `send` completes). Audio acquires `slots=2` but never calls `lease.inspect()` (in-process WAV decode) — burns PNG capacity without using it.
* **Why Static Analysis Missed It:** Semaphore pairing looks correct; lifetime coupling to network RTT + slow-consumer backpressure is cross-module.
* **Impact:** 2 slow image/audio requests → all further generated-output `503 busy`; self-DoS; audio DoSes image and vice-versa.
* **Recommended Fix:** Separate `PNG_SLOTS` vs no-slot audio; acquire late (just before `inspect()`, release immediately after); separate delivery quota, never hold slot across `stream_backend` await.

* **File/Module:** `src/foundry_router/forwarding/__init__.py:666-704,1014,1061-1063`, `src/foundry_router/credit.py:375-493`
* **The Issue:** `retain_full_cost=image or audio` never refines cost from `usageMetadata`. Image always bills `bound + ceiling`; audio always bills `10s * price` even though actual frames/tokens known (`OutputWavFacts.frames`, adapter usage). `MAX_TOKENS` truncation or text-only `STOP` still force-charges full image price while silently dropping artifact (`google_image_output.py:103`).
* **Why Static Analysis Missed It:** Looks like intentional conservative settlement; requires billing-domain reasoning.
* **Impact:** 1s audio billed as 10s; credit/quota diverge; disputed billing.
* **Recommended Fix:** Settle actuals (`ceil(frames/24000)*price`, `+image_price only if artifact_delivered`); expose `billed_artifact/billed_seconds` in receipt or document provider invoice evidence.

## Major

* **File/Module:** `src/foundry_router/api/common.py:36-73`, `src/foundry_router/api/routes/openai.py:380-383`
* **The Issue:** Embeddings `request_body()` never passes `deadline_monotonic`; stream loop has no timeout, appends whole chunk before size check — single large chunk spikes memory before 413. Responses path has outer `timeout_at` but loop never checks deadline intra-iteration.
* **Why Static Analysis Missed It:** Optional `deadline=None` looks benign; missing arg at call-site not flagged.
* **Impact:** Slowloris / memory amplification.
* **Recommended Fix:** Always pass `intake_deadline`; check `monotonic()>=deadline` inside loop; reject chunk that would exceed bound before `extend`.

* **File/Module:** `src/foundry_router/api/google_sealing.py:38-83`, `src/foundry_router/forwarding/__init__.py:464-483,854-864`
* **The Issue:** `validate_dispatch` runs *after* `build_upstream_body` (signatures injected before binding check); uses `is` identity (`key_configuration is not keys`, `backend_client._settings is not settings`) — brittle across `load_settings()` singleton vs fresh object; legacy doubles without `_settings` always fail; no `prepared.backend==dispatch backend` check here.
* **Why Static Analysis Missed It:** Needs runtime lifecycle model of settings/client objects + build-then-validate ordering.
* **Impact:** Spurious 503 after reload, or stale pricing/credential use on retry failover.
* **Recommended Fix:** Validate before build; compare fingerprint/generation values not `is`; re-resolve settings per attempt; check backend pinning in `validate_dispatch`.

* **File/Module:** `src/foundry_router/api/adapters/__init__.py:41-78`
* **The Issue:** Native branch does not check `continuation_policy` — missing `seal_context` silently falls back to `GoogleNativeAdapter` instead of error. Compat branch ignores `api_surface`. Forwarding hardcodes `get_adapter("google_ai_studio",...)`. Image-eligibility in `openai.py:178` calls without `seal_context` (safe today only because validator forbids `image+sealed`, fragile).
* **Why Static Analysis Missed It:** Each `raise` looks fail-closed; bug is omission.
* **Impact:** Future validator change → silent sealing bypass; 422 vs 502 confusion.
* **Recommended Fix:** Exhaustively validate `api_surface`; require `seal_context` presence matches policy (missing → raise, never fallback); pass provider from config.

* **File/Module:** `src/foundry_router/forwarding/__init__.py:724-733` vs `1728-1731`, `src/foundry_router/config/__init__.py:718-726`
* **The Issue:** Non-streaming gates `image/audio → require lease + cost`, sets `retain_full_cost`; streaming constructor never sets it, never checks lease. Relies solely on `check_request` stream rejection. Latent today (config rejects all image/audio), but mock bypass or future compat surface undercharges.
* **Why Static Analysis Missed It:** Each function locally correct; invariant spans functions.
* **Impact:** Undercharge of `+ceiling/+10s` reserve if streaming generation ever admitted.
* **Recommended Fix:** Mirror guard in `_forward_google_streaming` or assert non-streaming for generated types.

* **File/Module:** `src/foundry_router/backends/__init__.py:63-79,151-177`, `src/foundry_router/forwarding/__init__.py:1830-1836`
* **The Issue:** `_validate_url` with service-root endpoint (`...googleapis.com/`) → `configured_path=""` → any path on host passes (host-only allow-list for native). Sealed streaming builds `generateContent` (non-SSE) URL then runs SSE decoder.
* **Why Static Analysis Missed It:** Requires combining URL validation with endpoint-shape knowledge.
* **Impact:** Weakened egress allow-list; sealed-streaming 502/force-charge if enabled.
* **Recommended Fix:** Require `/v1beta/models/` prefix when `api_surface==native`; remove `seal→non-streaming method` special case.

* **File/Module:** `src/foundry_router/api/google_output_work.py:24-38,84-90`, `src/foundry_router/api/routes/openai.py:201`
* **The Issue:** Every image request does `await lease.ready()` → `inspect(_PROBE_PNG 1024×1024)` then a second `inspect(real_bytes)` — 2 subprocess spawns + 2×~3MB inflate per image.
* **Why Static Analysis Missed It:** Two correct bounded calls; cost only visible tracing lifecycle.
* **Impact:** 2× CPU/latency; doubles slot pressure.
* **Recommended Fix:** Probe once at startup/readiness, cache with TTL + failure invalidation; remove per-request `ready()`.

* **File/Module:** `src/foundry_router/api/google_pdf.py:221-314`, `src/foundry_router/api/google_output_work.py:116-182`
* **The Issue:** `inspect()` timeout wraps spawn+read, but `finally: await process.wait()` / `child.wait()` runs outside timeout with no bound. Wedged worker pins slot (`active` stuck).
* **Why Static Analysis Missed It:** `try/finally + kill` looks correct; missing `wait()` timeout needs async-cancellation reasoning.
* **Impact:** One wedged worker → persistent `503` until restart.
* **Recommended Fix:** `wait_for(wait(), timeout=1.0)` in cleanup; release slot, log `worker_reap_timeout`.

* **File/Module:** `src/foundry_router/credit.py:417,431` (`_estimate_audio_pool`)
* **The Issue:** `inputs = len(bytes)+...+64` (bytes-as-tokens, ~3× text-equivalent `ceil(chars/3)`); magic `10` seconds unexplained, no link to `profile.max_audio_seconds`.
* **Why Static Analysis Missed It:** Numeric economics, not types.
* **Impact:** Systematic over-reservation → false 503; under-reserve if generation >10s.
* **Recommended Fix:** Named `AUDIO_GENERATION_SECONDS_CEILING` linked to profile; document 1:1 conservatism or divide by token divisor.

* **File/Module:** `src/foundry_router/credit.py:388,414`, `src/foundry_router/config/google_output.py:49-52`
* **The Issue:** Exact `price != ceiling` float equality fail-closes entire pool on repr drift (`0.30000000000000004 != 0.3`).
* **Why Static Analysis Missed It:** Type-correct, logic-correct for exact values.
* **Impact:** Spurious `503 pricing_unavailable`.
* **Recommended Fix:** `math.isclose(..., rel_tol=1e-9)` or validate once at startup.

* **File/Module:** `src/foundry_router/auth/__init__.py:55-69`
* **The Issue:** No length bound before `compare_digest`/HMAC loop over N keys; `decode_state_key()` per request; deterministic caller scope linkable across requests.
* **Why Static Analysis Missed It:** Sees `compare_digest`+`hmac` and marks secure.
* **Impact:** Low-rate CPU DoS; rotation race.
* **Recommended Fix:** Reject `len>512` before loop; cache decoded scope key; document linkability intent.

## Suggestions

* **Dead-code carry:** `credit.py:274-324`, routing pinning `314-336`, forwarding `seal_context`/`output_lease` plumbing are prod-dead behind unconditional config `raise`. Gate behind `FOUNDRY_ENABLE_EXPERIMENTAL_*` or delete until gates pass; don’t describe as deployed.
* **Telemetry lie:** `routing/__init__.py:645,679` — `has_credit_capacity=True` set immediately before `append` with no `continue`; `not scored_candidates ⇒ has_credit==False` always, reason always `no_usable_credit_state`. Collapse or set from `assessment.state`.
* **Adapter swallow:** `routing/__init__.py:129-135` `except Exception → 422` with no redacted log. Add `logger.warning(backend_id, exc_type)` without body.
* **Media pre-walk:** `credit.py:522-554` walks full `data:...base64` through text estimator when pricing bound missing. Pre-reject `input_image/input_file` when no bound before text walk.
* **Canonical-base64 strictness:** `google_image_output.py:98`, `google_audio.py:80`, `google_video.py:156`, `google_pdf.py:111` — `b64encode(raw)!=encoded → 502` after paid upstream cost. Accept any `b64decode(validate=True)` and re-emit canonical.
* **JPEG cap inconsistency:** `google_raster.py:14,41-48` — JPEG `>128` rejects while PNG/WebP allow 384 and `_MAX_DIMENSION=384`. Unify with justification.
* **Sync raster on loop:** `google_raster.py:90-135` Huffman table builds (~1MB, Python loops) with no deadline on async path. Move to bounded worker with deadline checks.
* **PDF probe poisoning:** `google_pdf.py:148-184` — `self.probe` cached forever; one transient `False` → permanent 503. Clear on failure, TTL/retry.
* **Delivery lookup fragility:** `google_output_delivery.py:64-86` vs `main.py:407` — `scope["state"]` dict vs `request.state` attribute coupling is Starlette-version-dependent. Single accessor + transfer-assert test.
* **Platform/version brittleness:** `sys.platform=="linux"` ×3 + exact `pypdf==6.19.0` pin → silent 503 on bump/dev. Central `output_platform_ready()` + `>=6.19,<7` with self-test hash.
