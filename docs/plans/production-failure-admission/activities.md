# Activities

## Step-By-Step Activities

1. Independent review before requests. Record reviewer verdict in `evidence.md`. Do not proceed to live traffic on a rejected or conditionally-approved plan without closing conditions.
2. Resolve production references in memory only. Retrieve client/admin keys through captured token-authenticated vault reads. If the current operator lacks data access, grant temporary Secrets User on the production vault and remove precisely that assignment in `finally`. Never print fields from credential-bearing objects, log keys/headers/prompts/outputs/error bodies, or commit references.
3. Read-only baseline: `GET /health/live`, `GET /health/ready`, `GET /openai/v1/models`, `GET /admin/status`, `GET /metrics`. Snapshot canonical `credit_groups` (never sum backend views), backend health states, cooldown remaining, active/inflight reservations, reconciliation `stale`/`consecutive_failures`, and model catalog. Abort on unhealthy readiness or stale reconciliation that the operator does not explicitly accept.
4. Safe admission probes (sequential with short fixed spacing; each exactly once; on unexpected 429/5xx halt immediately with no live retry/failover — record, verify cleanup/readiness, and close with the remaining gate retained; stop on unexpected egress or reservation leak):
   - Missing/bad client auth → 401 with `WWW-Authenticate`, no egress.
   - Unknown model → 404 `model_not_found`, no egress.
   - Malformed body (e.g. wrong content type or invalid JSON shape) → 4xx, no egress.
   - Unsupported field: pre-specify before the run from `../../api/index.md` (first choice `previous_response_id`, second choice an unconfigured tool such as caller-executed function tools on an `fs-swarm` Azure pool) → 422, no egress. If every candidate field is supported by `fs-swarm` pools, record "not applicable + reason" rather than iterating live to force a 422.
   - After each probe: confirm zero active/inflight reservations via admin status and no backend request-counter increment attributable to the probe.
5. Bounded inference (only after admission probes pass; pool pinned at the baseline snapshot from the cheapest configured `fs-swarm` pool at runtime prices — same pool for both probes; any reselection requires operator re-confirmation; record pool alias only, no prices; at most two requests total):
   - One non-streaming Responses request: `max_output_tokens` 128, `store:false`, low reasoning effort where accepted, total deadline 180s / read 120s.
   - One streaming Responses request with the same bounds. Never retry after meaningful stream output begins; post-start failures are observed as SSE error events only.
   - Record HTTP/completion/usage/event types only. Require text delta + `response.completed` with terminal usage, no partial trailing frame, usage-matched local estimated debit (estimate, not Azure bill), and zero inflight/active reservations after settlement.
6. Observational failure-state checks: confirm admin health/cooldown fields, `Retry-After` contract (by inspection of exhausted-cooldown shape from local suite, not by inducing exhaustion), single-failover cap (two distinct backends max, by code path reference), and stream cleanup semantics. Expected `routing_decision` source is the structured log event (redacted fields only: model, selected backend or null, reason, estimated cost); `routing_decision_detail` is DEBUG-only and excluded from production INFO — if the decision event is not exposed in production diagnostics, record "not-observed" rather than inferring. Do not induce 429/5xx, reset credit, restart, redeploy, or change replicas.
7. Finalize: remove temporary vault access in `finally`, re-verify readiness, and document successes/failures plus remaining `fs-openclaw`/Table/cost gates in `evidence.md`. Evidence-only unless a defect requires an independently reviewed code correction. No commit/push after test without user request.

## Review Focus

- Bounded scope is actually bounded (probe counts, no retry-after-stream, no exhaustion probes, `fs-swarm` only).
- No-egress claim for each admission probe is verifiable via counters + reservation state, not assumed.
- Credit vs quota separation preserved; local debits labeled estimates.
- Metadata-only logging (no prompts/outputs/keys/headers/bodies).
- Production mutation explicitly prohibited and finally-guarded vault cleanup present.
