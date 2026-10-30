# Table production and autoscaling Risk Register

## Status: Planned

## Risks

| ID | Risk | Impact | Mitigation | Status |
| --- | --- | --- | --- | --- |
| R1 | Old consumed acceptance/deployment ledgers replayed | Unauthorized spend, ambiguous accounting rewritten | Fresh locked program ID; consume before dispatch/mutation; preserve old bytes and unresolved amounts | Open |
| R2 | Stale snapshot or overlapping old/new writers | Duplicate account allowance or lost debits | Fence+drain, fresh same-process snapshot, freeze and prove old replicas absent before successor, one-time seeds | Open |
| R3 | Partial Table seed/apply or lost acknowledgement | Unsafe retry/reset or partial financial state | Per-account intent/results persisted, empty-owned-state checks, read-only reconciliation and fresh reviewed recovery | Open |
| R4 | Old metadata bug or stale runtime version | Real settlement503/retained reservation | Current hash-bound release, SDK-wire/Azurite tests, four fresh live cases and actual restart | Open |
| R5 | Counter/cycle semantics lost during migration | Misleading historical debit metrics or automatic replenishment | Explicit counter continuity/lifetime choice, cycle-bound snapshot validation and durable seed tests | Open |
| R6 | Test app duplicates production account funds | Shared wallet overspend | Exclusive small allocation within account funds; no stale staging restart; aggregate reserved-estimate ledger | Open |
| R7 | 512 MB content mistaken for wire cap/context | Reject valid payloads or false upstream compatibility claims | Dated operation matrix, encoding/units evidence, unknown wire policy owned upstream, no token-byte mapping | Open |
| R8 | Larger bodies retain full parsing/serialization copies | OOM, event-loop stalls, auth/intake DoS | Admission before intake, weighted aggregate capacity, benchmark static resources, bounded incremental/spooled path if necessary | Open |
| R9 | Unknown Content-Length/model-last routes bypass bounds | Unbounded intake or wrong provider contract | Count real streamed bytes/resources; safe initial lease; parse then select operation policy, no caller provider override | Open |
| R10 | Generic cap change affects preserved providers | Unauthorized capabilities/cost/routing regression | Provider-owned bounds and fixture regression; preserve all non-Azure config/behavior; no live other-provider calls | Open |
| R11 | Table quota semantics assumed correct for Azure/all providers | Excess upstream admission or needless throttling | Source-backed actual group quotas/windows/token units; cross-worker acceptance; keep max1 if preserved providers lack safe proof | Open |
| R12 | Shared health eventual consistency treated as instantaneous | Extra failures during cooldown race | Measure convergence, conservative admission/failover fixtures, explicit operational limits and no-post-output retry | Open |
| R13 | Load-balanced local metrics mistaken for aggregate | Missing/double financial or traffic totals | Verified lifetime-aware OTLP or honest platform+Table alternative; shared gauges/counters nonadditive | Open |
| R14 | Static resource increase described as vertical autoscaling | Incorrect infrastructure/cost expectations | Supported static revision sizing; horizontal only, max3 and bounded exercise with cost packet | Open |
| R15 | Scale-down kills active stream/settlement | Truncated SSE or unowned reservation/debit | Proven shutdown drain, deadlines/shielded cleanup, persistent intent/reaper, actual transition tests | Open |
| R16 | Ingress or secretRef normalization changes during apply | Exposure, outage or credential/config drift | Exact effective hashes and original ingress; finite scoped ARM mutation; binding refusal before inference; restoration mandatory | Open |
| R17 | USD1 estimate confused with authoritative bill ceiling | Unexpected billed costs | Explicit local-estimate label,16attempt/128output/zero retry limits, conservative uncertain retention; separate infrastructure estimate | Open |
| R18 | Dirty deployed USER WORK overwritten | Production fix regression and user work loss | One writer, inventory and hash binding; never reset old plans/source/docs; feature-local reviewed amendments | Open |

## Open Decisions

All decisions below require concrete evidence and independent approval before their dependent phase; no unresolved decision authorizes unsafe implementation.

1. **D1 — Resource reuse:** which discovered existing app/identity/account/tables are compatible and exclusively owned? Default reuse parent resources; fresh owned tables only if necessary. Resolve before isolated mutation.
2. **D2 — Current release binding:** can the deployed digest be reused unchanged or does a verified candidate need rebuilding? Bind existing USER WORK; resolve before paid acceptance.
3. **D3 — Four-account Table initialization:** preserve debit/recovery totals by reviewed seeding or explicitly establish a new counter-lifetime baseline? Fresh remaining balances must be exact/conservative regardless. Resolve before production packet approval.
4. **D4 — Acceptance coverage and USD1 allocation:** select exact already available Azure deployments/account coverage, text/Anthropic/MAI/embeddings cases and disjoint slots, with actual configured local estimates. Four isolated cases are mandatory; excluded migration operation coverage needs reviewer acceptance, not an invented pass.
5. **D5 — Payload wire ownership/units:** authoritative MB definition, actual combined-content calculation, encoding overhead and platform wire/time constraints remain unresolved. Prefer upstream-owned unknown wire policy and resource admission, never invent512MiB JSON ceiling.
6. **D6 — Minimal safe intake architecture:** bounded full parse in sufficiently sized static container versus private ephemeral spool/incremental parsing/serialization; prove full supported-content aggregate capacity without arbitrary lower size caps. Unknown unbounded wire support incompatible with finite storage is an explicit architecture blocker, not a `None` shortcut.
7. **D7 — Azure embeddings/Anthropic/MAI bounds:** obtain exact Azure/model/operation sources; current local text/image caps do not establish upstream maxima. Resolve unsupported features separately from supported payload size.
8. **D8 — Shared quota semantics/capacity:** validate actual Azure reservation/token/window rules and whether existing256record/48KiB Table design fits; preserved providers cannot gain guessed settings. Safe whole-app scaling alternative or max1 blocker must be explicit.
9. **D9 — Metrics alternative:** reuse verified existing collector if available; otherwise prove complete platform+canonical-state operational visibility and label local counters honestly. New collector requires concrete separate infrastructure justification.
10. **D10 — Static CPU/memory and autoscaler policy:** choose supported pair, weighted admission, exact concurrency threshold/stabilization and cost estimate from benchmarks. Initial target min1/max3 is bounded judgement, not a measured final setting; max2 acceptance precedes max3.
