# Existing-account cross-RG Table verification

## Status: Implemented

Use an operator-approved dedicated hardened account in the shared resource group, then attach an isolated app from the existing test deployment group. Verify table-scoped identity access without mutating the existing parent account. Production stays memory/one.

Cross-RG attachment, identical redeployment, managed-identity reservation operations and configured synthetic balance/reservation persistence across targeted container restart passed. Checked parent hardening, SKU and tags remained unchanged. Real inference and production cut-over remain pending.

- [Inputs](inputs.md)
- [Activities](activities.md)
- [Outputs](outputs.md)
- [Exit criteria](exit-criteria.md)
- [Risks](risk-register.md)
- [Evidence](evidence.md)
