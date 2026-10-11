# Live verification risks

| ID | Risk | Impact | Mitigation | Status |
| --- | --- | --- | --- | --- |
| R1 | Credential committed, logged, or displayed | Secret exposure | Out-of-band env/vault only; numeric-only evidence; pre-dispatch refusal on locally detectable credential failures; upstream validity remains unproven until dispatch | Open |
| R2 | Prompts/outputs/error bodies recorded | Data exposure | Record numerics only; halt-and-review rule for evidence content | Open |
| R3 | Retry after stream output or ambiguous failure | Double spend, repeated generation | Fixed cases, durable pre-dispatch intent, exclusive lock, validated per-case results; uncertain or failed cases block the entire run | Open |
| R4 | Budget overrun beyond five dispatches | Unexpected spend | Five fixed IDs, no spare probe/retry slot; persistent cumulative accounting survives restart | Open |
| R5 | Success overgeneralized to other models/billing/production | Unsafe rollout | Explicit per-exact-model scope and non-claims in evidence | Open: live gate |
| R6 | Live run against production configuration | Production impact | Dedicated test configuration only; memory/single-replica; no production changes | Open |
| R7 | Public usage and settlement share a mapping defect | False live acceptance | Independent bounded upstream observer; compare provider/public usage and per-request canonical credit-group deltas | Open: harness gate |
| R8 | Populated invalid upstream credential passes local readiness | Dispatched authentication rejection | Count provider 401/403, retain sanitized statuses, halt; no cycling/retry | Open: live gate |
| R9 | Stream or diagnostic hangs; capture grows without bound | Unbounded run or data retention | Explicit time/byte/frame/poll bounds; incremental parsing and allow-listed output; failure blocks successors | Open: harness gate |

## Open Decisions

- Exact operator-selected models and test prices (required before Stage 1).
- Credential supply mechanism (env vs token-authenticated vault reads).

Harness implementation and offline/contextual review remain pending before live use.
