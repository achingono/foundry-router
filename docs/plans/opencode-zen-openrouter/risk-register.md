# Zen/OpenRouter risks

| ID | Risk | Impact | Mitigation | Status |
| --- | --- | --- | --- | --- |
| R1 | New provider falls through Azure/Google/generic transport | Wrong URL/wire/accounting | Explicit per-provider dispatch and API regressions | Open |
| R2 | Root/auth ambiguity across four HTTPS roots | Wrong target or credential exposure | Exact root/Bearer contract and confinement tests per provider | Open |
| R3 | Zen translation dialect leaks into pass-through (or vice versa) | Upstream 4xx or silent shape mismatch | Separate adapter paths with dialect-absence tests | Open |
| R4 | OpenRouter-only fields forwarded or caller-controlled routing | Cost/routing hijack, attribution leak | Strict allow-list; rejection-before-admission tests | Open |
| R5 | Google capability assumptions leak into OpenRouter text path | Unsupported shapes or coupling | Independent context; no Google helper imports | Open |
| R6 | Shared forwarding changes existing behavior | SSE/settlement regressions | Unchanged Google + generic oracles and lifecycle suites | Open |
| R7 | Ambiguous 5xx repeats generation | Double spend/output | Single-shot attempts and conservative settlement | Open |
| R8 | Local tests interpreted as universal support | Unsafe rollout | Exact upstream/model live gates; no live claims | Open: live gate |
| R9 | Zen inherits Azure retries or failure refunds | Repeated generation or under-accounted spend | Separate attempt policy from wire helpers; both stream modes tested with retry_attempts > 1 and retained usage/estimate settlement; review finding PR-1 | Open: implementation verification |
| R10 | Zen accepts foreign request fields or an incompatible configured model | Late rejection after admission or unsupported upstream behavior | Dedicated bounded request allow-list; zero-admission negative tests; operator owns selection of a Responses-compatible model without a catalog-validation claim; review finding PR-2 | Open: implementation/live verification |

## Open decisions

- Zen chat-models (`/chat/completions` rows in the Zen table): follow-up provider
  extension vs documented use of generic `openai_compatible`; current plan keeps
  them out of scope.
- OpenRouter embeddings live shape: implementation allows explicit declaration,
  but live verification needs an operator-selected exact model before any
  compatibility statement.
- Optional OpenRouter attribution headers (`HTTP-Referer`, `X-Title`): router
  sends none in this phase; any future static operator-owned values need a
  separate redaction/security review.
