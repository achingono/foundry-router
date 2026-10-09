# Production failure/admission verification

## Status: Partially implemented

Admission, settlement and observable failure-state verified on the existing memory/one production app for one pinned pool (`gpt-6-luna`); both test dispatches were served by the `fs-openclaw` backend for that pool. No configuration, image, secret-value, credit-balance, ingress, or replica change. No Table cut-over. Live upstream 429/5xx failover remains unverified by design. Evidence-only; no defect required a code correction.

## Companion Documents

- [Inputs](inputs.md)
- [Activities](activities.md)
- [Outputs](outputs.md)
- [Exit Criteria](exit-criteria.md)
- [Risk Register](risk-register.md)
- [Evidence](evidence.md)

## Objective

Establish what the current production router actually does on admission rejections (no-egress paths) and on observable failure state (health/cooldown/readiness/metrics/reservation cleanup), using only safe probes plus at most one bounded `fs-swarm` non-streaming and one streaming Responses request to prove settlement still closes. This addresses the admission + settlement + observable failure-state portion for `fs-swarm`; live upstream 429/5xx failover remains unverified by design (no induced exhaustion) without mutating production.

## Scope

## In Scope

- Read-only production checks: liveness, readiness, model discovery, admin status (health/credit/groups), metrics, reconciliation staleness.
- Safe admission probes that must not dispatch upstream: bad auth (401), unknown model (404 `model_not_found`), malformed body (4xx), unsupported field where applicable (422) — metadata status/type only.
- At most two inference probes on one operator-confirmed lowest-cost `fs-swarm` pool: one non-streaming + one streaming Responses request (`max_output_tokens` 128, `store:false`, low reasoning effort where accepted), with terminal usage, debit reconciliation as local estimate, and zero inflight/active reservations after each.
- Observational failure-state verification: backend health states, cooldown fields, `Retry-After` propagation contract, no-retry-after-stream rule (by inspection + prior suite, not by breaking a live stream), `routing_decision` scope where exposed via diagnostics.

## Out of Scope

- `fs-openclaw` inference or failover between resources (remains unverified).
- Inducing real upstream 429/5xx, quota-exhaustion probes, ramp or soak tests.
- Embeddings live verification (remains unverified unless operator explicitly extends scope at runtime).
- Table-backed inference, authoritative cost reconciliation, multi-worker metrics aggregation, production cut-over.
- Any production mutation: config/secret/image/table/grant/ingress/replica changes, credit resets, log or secret retention.

## Entry Criteria

- Production remains `stateBackend: memory` with `min/maxReplicas: 1` (see `production-foundry/evidence.md`).
- Prior 12-request `fs-swarm` inference scope retained (`production-inference/evidence.md`); this plan does not replay it.
- Real production traffic authorization from the current operator session.
- Independent plan review approval before any live request.

## Exit Criteria

See `exit-criteria.md`.

## Roles

- Owner: implementing session
- Reviewer: independent session (different model or session, required before live traffic)
- Approver: operator
