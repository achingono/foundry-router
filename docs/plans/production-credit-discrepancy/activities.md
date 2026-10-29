# Production credit discrepancy investigation activities

## Step-By-Step Activities
1. Inspect tree, canonical accounting/operations documentation, deployed configuration and relevant tests.
2. Read authenticated admin status and metrics, keeping credentials inside the diagnostic process; compare canonical account debits with deployment-labelled request costs.
3. Discover Foundry accounts across accessible subscriptions and query current/prior billing-period dates. Compare actual dates with configured cycle days.
4. Query sanitized rejection details and period-specific provider metrics/costs; distinguish USD estimates from CAD reported billing and incomplete recent data.
5. Reproduce missing-usage settlement and cached-input pricing locally; run existing credit/recovery tests.
6. Record findings and scoped remediation recommendations. This investigation does not mutate production or implement a fix. Any implementation follows a separately reviewed plan and the repository verification workflow.

## Review Focus
- Do not treat the operator's three-day chart as cycle-to-date fs-swarm usage.
- Do not sum duplicated account balances from backend entries.
- Preserve conservative financial settlement while exposing all actual ledger debits in diagnostics.
- Any future memory restart requires fresh, conservative all-account seeds and drained writers; changing a seed or cycle day alone is not a historical reconciliation.
