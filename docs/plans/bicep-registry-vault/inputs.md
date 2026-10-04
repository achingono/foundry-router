# Registry/Vault Inputs

## Required Inputs
| Input | Source | Owner |
|---|---|---|
| Verified workload modules | 49107a5 and container evidence | Infrastructure |
| Current new/existing scopes and role formulas | infra/main.bicep and access modules | Infrastructure |
| Baseline shared ACR and dedicated vault | Existing synthetic deployment | Operations |

## Optional Inputs
- Empty test scopes for new-resource runtime deployment, not required for synthetic existing/existing baseline.

## Input Validation Checklist
- [x] Sources and canonical documentation inspected in preceding increments.
