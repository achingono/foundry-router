# Production credit discrepancy investigation inputs

## Required Inputs

| Input | Source | Owner |
|---|---|---|
| Reported Responses 503 and request ID | Operator, October 29, 2026 | Operations |
| Production revision, pinned configuration and authenticated diagnostics | Read-only Azure control plane and router admin/metrics | Investigator |
| Account/subscription mapping and billing-period records | Azure resource discovery and Microsoft.Billing API | Investigator |
| Usage and reported costs | Azure Monitor and Cost Management | Investigator |
| Accounting contract and implementation | [Shared-credit operations](../../operations/shared-resource-credit.md), credit, forwarding and metrics modules | Maintainers |

## Optional Inputs
_Inputs that improve the phase but are not blockers._
- Operator reports roughly $12 from Foundry metrics over October 26–29. That time window is not the verified fs-swarm billing cycle.

## Input Validation Checklist
- [x] Current deployed configuration and unique credit-group balances read without inference.
- [x] Billing periods queried from each subscription containing discovered Foundry accounts.
- [ ] Complete, currency-normalized billing evidence through today's traffic. Azure billing rows returned no October 29 charges.
