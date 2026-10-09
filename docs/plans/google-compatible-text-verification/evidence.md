# Compatibility verification evidence

| Item | Reference | Notes |
| --- | --- | --- |
| User execution inputs | Supplied secret and free-tier authorization | Existing key array; no key values persisted |
| Retained limits | [Ledger](../google-ai-routing-order/ledger-native-text-2026-10-08.json) | Project-1 19 requests; projects 2–5 14 each before this stage |
| Independent plan review | [Review](plan-review.md) | Ledger baseline/resume and usage consistency amendments cleared before runner edits |
| Runner review | [Contextual review](implementation-review.md) | 27 independently rerun synthetic tests; all Critical/Major findings cleared |
| Local verification | 27 focused cases; full suite 1,794 passed, 3 platform skips, 18 deselected | 89.79% runtime coverage; 99.35% verification-runtime and 88.98% stage coverage. Ruff/format/mypy pass; exact body/auth, metered cleanup, bounds, malformed usage/overrun and durable resume/lock |
| Live verification | Results (local-only `results.json`) | Five nonstream dispatches: provider 200, public 502, known usage 7 input/2 output each; all five failed public compatibility; no streams dispatched |
| Accounting | [Retained ledger](../google-ai-routing-order/ledger-native-text-2026-10-08.json) | Each reserve 1,088 retained despite actual nine tokens; synthetic debit $0.009 each; reservations cleared, no overrun |

The guard validates numeric usage independently of public translation. These observations
establish provider reachability and conservative failed-response settlement, not successful
public compatible Responses. The provider response schema/rejection cause was not recorded;
it must not be inferred from HTTP codes. Every project is halted for this stage on resume.
Project-1 cumulative totals are 20 requests/18,368 reserved tokens; projects 2–5 are each
15 requests/12,928 tokens. Production is unchanged. A new diagnostic contract requires review
before any further provider traffic; this stage never retries its failed cases.
