# Typed registry and vault provisioning

## Status: Implemented

Subsequent work completed the [public typed interface](../bicep-public-interface/index.md); deferred-interface references in this plan describe its historical scope.

Complete provisioning ownership by extracting new ACR/Key Vault resources and their same-resource scoped grants. Existing attachment paths remain in their target scopes. The flat root API, credential handling, exact resource identities/GUID formulas and verified memory baseline remain compatible.

All four registry/vault combinations and Table/new passed template validation. The synthetic existing/existing memory baseline redeployed and passed smoke checks. New-resource runtime convergence, real inference and deployed Table runtime remain unverified.

- [Inputs](inputs.md)
- [Activities](activities.md)
- [Outputs](outputs.md)
- [Exit criteria](exit-criteria.md)
- [Risk register](risk-register.md)
- [Evidence](evidence.md)
