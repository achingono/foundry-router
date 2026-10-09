# Cost reconciliation evidence

| Item | Reference | Notes |
| --- | --- | --- |
| Existing replacement behavior | Memory/Table apply_reconciled_remaining | Unsafe for delayed billing data; new atomic ceiling required |
| Official API inspection | [Query Usage](https://learn.microsoft.com/en-us/rest/api/cost-management/query/usage?view=rest-cost-management-2025-03-01) | Public ARM POST, scoped Custom query, typed columns/rows, paginated results; fetched 2026-10-08 |
| Billing data semantics | [Cost data availability](https://learn.microsoft.com/en-us/azure/cost-management-billing/costs/understand-cost-mgt-data) | Azure documents 8–24-hour typical EA/MCA and up-to-72-hour PAYG availability; open-period charges are estimates |
| Plan review | [Review](plan-review.md) | Separate session cleared final contract; mapping fingerprint and concrete typed response revisions accepted |
| Focused verification | 55 new unit cases; existing reconciliation/shared-credit/main regressions | Exact transport, bounded input/pagination, stale policy, concurrent debit, delayed-read rollover, cancellation and cleanup |
| Full suite | 1,767 passed; 3 platform skips; 18 deselected | 89.64% total coverage; new config/provider/types each over 92%. Initial sandbox loopback restriction resolved by rerun with required access |
| Real Azurite | 15 passed | Existing distributed-state tests plus concurrent ceilings, preserved inflight debit and restart non-replenishment |
| Quality/runtime | Ruff check/format, strict mypy 69 files; Docker | Python 3.12 network-disabled app/config/decimal/shutdown smoke passed; conditional SonarQube script absent |
| Contextual review | [Review](implementation-review.md) | All Critical/Major findings cleared; final JSON depth suggestion implemented and tested |
| Live Azure | Unverified | No billing query, permission grant or production change performed |
