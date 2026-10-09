# Compatibility verification evidence

| Item | Reference | Notes |
| --- | --- | --- |
| User execution inputs | Supplied secret and free-tier authorization | Existing key array; no key values persisted |
| Retained limits | [Ledger](../google-ai-routing-order/ledger-native-text-2026-10-08.json) | Project-1 19 requests; projects 2–5 14 each before this stage |
| Independent plan review | [Review](plan-review.md) | Ledger baseline/resume and usage consistency amendments cleared before runner edits |
| Runner review | [Contextual review](implementation-review.md) | 27 independently rerun synthetic tests; all Critical/Major findings cleared |
| Local verification | 27 focused cases; full suite 1,794 passed, 3 platform skips, 18 deselected | 89.79% runtime coverage; 99.35% verification-runtime and 88.98% stage coverage. Ruff/format/mypy pass; exact body/auth, metered cleanup, bounds, malformed usage/overrun and durable resume/lock |
| Live verification | Pending | No provider dispatch or production change yet |
