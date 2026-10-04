# Container Modules Inputs

## Required Inputs
| Input | Source | Owner |
|---|---|---|
| Verified resource extraction | c618ff2, extraction evidence | Infrastructure |
| Current workload settings/secret mapping | infra/main.bicep | Infrastructure |
| Synthetic baseline | Existing deployment, namespaced vault secrets and image | Operations |

## Optional Inputs
- Real inference configuration remains outside this refactor.

## Input Validation Checklist
- [x] Current template and canonical operations/architecture documentation inspected.
