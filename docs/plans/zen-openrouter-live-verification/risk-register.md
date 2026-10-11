# Live verification risks

| ID | Risk | Impact | Mitigation | Status |
| --- | --- | --- | --- | --- |
| R1 | Credential committed, logged, or displayed | Secret exposure | Out-of-band env/vault only; numeric-only evidence; pre-dispatch refusal on missing credential | Open |
| R2 | Prompts/outputs/error bodies recorded | Data exposure | Record numerics only; halt-and-review rule for evidence content | Open |
| R3 | Retry after stream output or ambiguous failure | Double spend, repeated generation | Sequential stages, no-retry rule, persistent halt on ambiguity | Open |
| R4 | Budget overrun beyond six dispatches | Unexpected spend | Operator-approved finite budget; record-before-next-dispatch | Open |
| R5 | Success overgeneralized to other models/billing/production | Unsafe rollout | Explicit per-exact-model scope and non-claims in evidence | Open: live gate |
| R6 | Live run against production configuration | Production impact | Dedicated test configuration only; memory/single-replica; no production changes | Open |

## Open Decisions

- Exact operator-selected models and test prices (required before Stage 1).
- Credential supply mechanism (env vs token-authenticated vault reads).
