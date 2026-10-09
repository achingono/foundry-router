# Cost reconciliation evidence

| Item | Reference | Notes |
| --- | --- | --- |
| Existing replacement behavior | Memory/Table apply_reconciled_remaining | Unsafe for delayed billing data; new atomic ceiling required |
| Official API inspection | [Query Usage](https://learn.microsoft.com/en-us/rest/api/cost-management/query/usage?view=rest-cost-management-2025-03-01) | Public ARM POST, scoped Custom query, typed columns/rows, paginated results; fetched 2026-10-08 |
| Billing data semantics | [Cost data availability](https://learn.microsoft.com/en-us/azure/cost-management-billing/costs/understand-cost-mgt-data) | Azure documents 8–24-hour typical EA/MCA and up-to-72-hour PAYG availability; open-period charges are estimates |
| Plan review | [Review](plan-review.md) | Separate session cleared final contract; mapping fingerprint and concrete typed response revisions accepted |
| Local/live verification | Pending | No Azure billing query, permission grant or production change performed |
