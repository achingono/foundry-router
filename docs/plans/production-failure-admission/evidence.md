# Evidence

## Evidence Log

| Item | Reference | Notes |
|---|---|---|
| Plan status | This plan | **Planned**; no live traffic executed yet; independent review approved with findings addressed |
| Scope basis | `../production-foundry/evidence.md`, `../production-inference/evidence.md` | Memory/one; 12-request `fs-swarm` inference passed; `fs-openclaw`/failure-admission/Table cut-over remain unverified |
| Contract basis | `../../api/index.md`, `../../features/routing.md`, `../../operations/index.md` | Admission/failover/cooldown/streaming contracts referenced, not redefined |
| Local regression basis | `tests/unit/test_main.py` | Admission, cooldown, single-failover, SSE-error-without-failover coverage exists locally |
| Plan review | Independent session | Approved with findings (1 Major + 4 Minor, all doc-clarifications); dispositions applied before live traffic: gate-closure reworded to admission/observable-state portion with live 429/5xx failover retained as unverified, 422 fields pre-specified, `routing_decision` source/redaction clarified, inference pool pinned at baseline, sequential spacing with halt-on-429/5xx stated |
| Live execution | Production app | Pending — bounded admission + at most two `fs-swarm` Responses probes per `activities.md` |

## Live results — executed 2026-10-09 (operator-authorized, `fs-swarm`-pool scope)

Status: **Partially implemented** (admission + settlement + observable failure-state verified for one pool; live upstream 429/5xx failover remains unverified by design).

No prompts, outputs, credentials, subscription IDs, endpoints, or deployment IDs retained. All debits are local estimates, not Azure billed amounts. Production config/image/secrets/tables/grants/ingress/replicas unchanged; production remains memory/one. Concurrent non-test production traffic was observed during the run; deltas below separate test-attributed series from background movement.

### Baseline (before probes)

| Item | Observation |
|---|---|
| Liveness | HTTP 200 `{"status":"alive"}` |
| Readiness | `ready:true`; all checks true (config, backends, deployments, models, client/admin auth, credit config, pricing, rate-limit share) |
| Models | 8 IDs: six pools plus `codex-auto-approve`, `codex-auto-review` aliases |
| Backends | 12 total, all `ACTIVE`, zero nonzero-cooldown, zero active reservations, zero inflight |
| Credit groups | `fs-openclaw` avail ~0.0799 `USABLE`; `fs-swarm` avail ~11.6862 `USABLE`; both zero inflight/active |
| Reconciliation | `stale:false`, zero consecutive failures |
| Metrics | `requests_total`, `credit_available_usd`, `credit_group_available_usd`, `estimated_cost_usd_total`, latency histogram families present |
| Pinned pool | `gpt-6-luna` (cheapest configured pool at runtime prices); embeddings out |

### Admission matrix (sequential, short spacing; one shot each)

| Probe | Result | Egress evidence |
|---|---|---|
| No-auth model discovery | HTTP 401 `detail` only | No counter series created |
| Bad-auth Responses | HTTP 401 `detail` only | No counter series created |
| Unknown model | HTTP 404 `model_not_found` | No counter series created |
| Malformed body | HTTP 422 `invalid_request` | No counter series created |
| `previous_response_id` (pre-specified 422 candidate) | HTTP 400 `invalid_request_error` (observed 400, not 422) | One backend-labeled 400 series with multi-second latency: apparent upstream provider rejection, zero-charge (no cost-series movement); zero active/inflight and zero cooldown after |

No live retry was performed on any probe; no 429/5xx was induced or observed on test traffic.

### Inference settlement (pinned pool `gpt-6-luna`, `max_output_tokens` 128, `store:false`)

| Request | Result | Usage | Settlement |
|---|---|---|---|
| Non-streaming Responses | HTTP 200 `completed` | input 7 / output 13 / total 20 | Test-attributed 200 series +1; cost total matches 2-request local estimate exactly (see below) |
| Streaming Responses | HTTP 200, 17 SSE events (`created`, `in_progress`, `output_item.added`, `content_part.added`, 9× `output_text.delta`, `done` chain, exactly one `response.completed`), no partial trailing frame | Terminal usage input 7 / output 13 / total 20 | Same 200 series +1 (total +2); combined local estimated debit 0.0000144 at operator prices |

Reservations sampled before the inference block and at close: zero active/inflight both times; per-request intermediate state not separately sampled. No retry after streaming output began. No `Retry-After` observed (no exhaustion path exercised).

### Failure-state snapshot (at close)

| Item | Observation |
|---|---|
| Readiness | `ready:true` |
| Backends | All `ACTIVE`, zero nonzero-cooldown, zero active reservations, zero inflight |
| Credit groups | `fs-openclaw` avail ~0.0535 `USABLE`; `fs-swarm` avail ~11.6862 `USABLE`; zero inflight/active both |
| Reconciliation | `stale:false`, zero consecutive failures |
| Routing coverage | Both inference dispatches served by the `fs-openclaw` backend for the pinned pool (test-attributed `requests_total` +2 on that backend/status 200); the `fs-swarm` backend for this pool was not exercised — no both-resource claim |
| Background traffic note | During the run, one non-test 200 on another pool and `fs-openclaw` group avail drift (~0.0799 → ~0.0535 with matching cost-total movement) were observed; test-attributed series are reported separately above |

### Close

- Temporary vault access: none created — direct captured reads succeeded with existing access, so no grant removal was needed. All key material and response bodies held in owner-only `/tmp` files verified deleted (`ls /tmp/.fr_*` → no matches).
- Auth retrieval used JSON-list client/admin secrets (first client entry for requests, single admin entry for diagnostics); values never logged or committed.
- `routing_decision` log event: not-observed in production diagnostics (per plan rule, not inferred).
- Remaining gates: `fs-openclaw`-selected inference for other pools, failover between resources, live upstream 429/5xx failover, Table-backed inference, embeddings, authoritative cost reconciliation, deployed metrics aggregation, production cut-over — all still unverified. Production stays memory/one.
