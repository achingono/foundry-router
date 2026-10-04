# Bicep Typing Inputs

## Required Inputs

| Input | Source | Owner |
|---|---|---|
| Verified memory baseline | Previous validation plan; commit 3e47ba3 | Infrastructure |
| Shared-type reference | Famorize iac/types.bicep and consumers | Infrastructure |
| Current deployment API | infra/main.bicep, committed parameter files, deploy workflow | Infrastructure |
| Module resource identity and scope | Existing access and storage modules | Infrastructure |

## Optional Inputs
- Azure baseline deployment and synthetic vault configuration for post-change checks.

## Input Validation Checklist
- [x] Current sources and canonical operations docs inspected.
- [x] User selected Bicep typing as the next phase.
