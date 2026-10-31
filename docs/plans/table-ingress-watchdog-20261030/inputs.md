# Isolated Ingress Watchdog Inputs

## Required Inputs

| Input | Source | Owner |
|---|---|---|
| Current G1 acceptance and rejection evidence | [G1 resume evidence](../table-production-autoscaling/g1-ready-finish-resume/evidence.md) | Coordinator |
| Existing runner/final-DENY protocol and fresh four-case G1 constraints | [Resume runner](../../../scripts/quality/table_production_acceptance_resume.py), [G1 exit criteria](../table-production-autoscaling/exit-criteria.md) | Coordinator |
| Dedicated internal ACA environment/VNet reachability, gateway network boundary, and private DNS evidence | Microsoft Learn and disposable isolated test only | Infrastructure owner |
| ACA HTTP diagnostic settings and calibrated ingress-denial evidence | Microsoft Learn and non-paid disposable app test | Observability/infrastructure owner |
| Gateway fault model, request routes, heartbeat/expiry bounds, and cost envelope | This design; independent reviewer | Design owner |
| Fresh four-case budget, effective zero-retry/failover policy, financial verifier and independent operator permission matrix | Separately reviewed packet and feasibility evidence | Operator/reviewer |
| Stage authorization and exact infrastructure/execution packets | Operator approved all stages in principle; exact packets and independent review remain required | Operator/reviewer |

## Optional Inputs

- Azure Firewall/NAT, APIM, Front Door, or private-network options, if they demonstrate the same fail-closed lease property without an ACA-origin bypass.

## Input Validation Checklist

- [x] Existing G1 scope is isolated; production remains memory-backed with one replica.
- [x] The current independent packet review finding is reproduced in the design problem statement.
- [ ] A new dedicated internal ACA environment/VNet is planned; the existing shared environment is excluded as a target.
- [ ] Cost, operations owner, and acceptable lease expiry bound are approved.
- [ ] No prior G1 approval is carried into this new topology.
