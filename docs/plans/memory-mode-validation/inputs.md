# Memory-mode Validation Inputs

## Required Inputs

| Input | Source | Owner |
|---|---|---|
| Current conditional storage declarations and compiled ARM | `infra/main.bicep` | Infrastructure |
| Reproduced memory failure and Table-mode success | Azure group validation | Infrastructure |
| Deployment constraints | `docs/operations/index.md`, `infra/README.md` | Operations |
| Shared registry and empty vault | Operator-selected shared resource group | Operator |

## Optional Inputs
- Real backend credentials for forwarding smoke tests; otherwise use a clearly labeled synthetic backend without outbound inference.

## Input Validation Checklist
- [x] Current template and staging defaults inspected.
- [x] Operator approved synthetic backend and dedicated compatible vault; vault write permissions established.
