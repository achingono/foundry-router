# Two-replica synthetic Table verification

## Status: Implemented

Verify two deployed test replicas against the existing isolated Table account. Production cut-over, real inference and existing-account cross-RG runtime remain separate gates.

Two replicas converged without manual restart. Synchronized managed-identity adapter reservations, matching shared totals, replica-local app diagnostics and targeted container restart persistence passed. This is synthetic state verification, not real inference or production cut-over.

- [Inputs](inputs.md)
- [Activities](activities.md)
- [Outputs](outputs.md)
- [Exit criteria](exit-criteria.md)
- [Risks](risk-register.md)
- [Evidence](evidence.md)
