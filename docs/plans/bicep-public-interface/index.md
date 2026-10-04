# Public typed deployment interface

## Status: Implemented

Add an opt-in typed entry point over the existing flat template. Reuse the existing orchestration and resource owners; CI continues using main.bicep. Registry, vault and state selections use sealed discriminated unions. Password remains a separate secure parameter.

Typed schema/parameter mapping and Azure validation passed. The synthetic existing/existing memory baseline redeployed and passed health/auth/models/admin/metrics checks. Real inference, new-resource runtime convergence and Table runtime remain unverified.

- [Inputs](inputs.md)
- [Activities](activities.md)
- [Outputs](outputs.md)
- [Exit criteria](exit-criteria.md)
- [Risks](risk-register.md)
- [Evidence](evidence.md)
