# Production Foundry resource configuration

## Status: Implemented

Deploy the approved two-resource/six-model topology with shared resource credit, memory state and one replica. Production registry resides in another subscription in the same tenant. Environment values and keys remain local/vault-only.

Production configuration deployment and readiness/model/group/auth checks passed. Production inference and Table-state cut-over remain unverified; the app remains memory-backed with one replica.

- [Inputs](inputs.md)
- [Activities](activities.md)
- [Outputs](outputs.md)
- [Exit criteria](exit-criteria.md)
- [Risks](risk-register.md)
- [Evidence](evidence.md)
