# Table runtime validation

## Status: Implemented

Fix Azure async transport packaging and verify a separate synthetic Table-backed app, leaving production and the memory baseline untouched. Verify token-only table access, readiness and persistence before considering multi-replica cut-over.

One-replica deployment, managed-identity readiness, independent adapter accounting/cooldown checks and persisted estimate across app restart passed. Two-replica deployment and real inference remain unverified; production stays memory/one.

- [Inputs](inputs.md)
- [Activities](activities.md)
- [Outputs](outputs.md)
- [Exit criteria](exit-criteria.md)
- [Risks](risk-register.md)
- [Evidence](evidence.md)
