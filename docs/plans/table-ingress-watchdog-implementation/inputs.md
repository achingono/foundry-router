# Watchdog Implementation Inputs

## Required Inputs
| Input | Source | Owner |
|---|---|---|
| Reviewed design and prior findings | [Design](../table-ingress-watchdog-20261030/design.md), [review](../table-ingress-watchdog-20261030/design-review.md) | Coordinator |
| Current G1 accounting, receipt and restart requirements | [G1 exit criteria](../table-production-autoscaling/exit-criteria.md), [phase-1 packet](../table-production-autoscaling/phase1-packet.md) | Operator |
| Existing pure accounting and dispatch helpers | [Acceptance harness](../../../scripts/quality/table_production_acceptance.py), [focused tests](../../../tests/unit/test_table_production_acceptance.py) | Implementer |
| Independently reviewed implementation plan | This folder | Reviewer |
| Pinned signer public keys and isolated test-only credentials | Separate reviewed operational provisioning, never tracked | Operator |
| Trusted-clock measurements, VM/ACA/VNet/Blob details, identity matrix, costs and diagnostic calibration | Future isolated, explicitly scoped Azure feasibility packet | Infrastructure owner |
| Remaining program liabilities and fresh four-case budget | Private exact G1 packet and independent reviewer | Operator/reviewer |

## Optional Inputs
- Existing mocked test fixtures; historical observations are not approval or fresh evidence.

## Input Validation Checklist
- [x] The design has an independent design-only approval; the user approved stages in principle.
- [x] This implementation plan is independently reviewed with no unresolved Critical/Major plan findings; host-suspension design remains a separate pre-implementation blocker.
- [ ] Azure feasibility and the separately reviewed exact infrastructure and G1 packets exist before their respective gates.
- [ ] No old case-3 slot, packet, ledger allocation, or results are reused as fresh acceptance.
