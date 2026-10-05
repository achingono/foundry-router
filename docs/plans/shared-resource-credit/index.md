# Shared resource credit accounting

## Status: Implemented (runtime and production configuration)

Production topology uses 12 deployment backends sharing two resource credit accounts. Credit-group membership preserves backend-owned health and quota-group-owned provider quota. Completed production inputs remain gitignored.

Runtime implementation and local memory/Table/Azurite verification are recorded in
[evidence](evidence.md). Final independent implementation review approved all lifecycle fixes. Subsequent [production configuration](../production-foundry/evidence.md) deployed and passed readiness/topology/auth checks; production inference and Table cut-over remain pending.

- [Inputs](inputs.md)
- [Activities](activities.md)
- [Outputs](outputs.md)
- [Exit criteria](exit-criteria.md)
- [Risks](risk-register.md)
- [Evidence](evidence.md)
- [Contextual implementation review](review.md)
- [Approved recovery amendment for independent Major findings](recovery-amendment.md)
- [Recovery implementation and fault evidence](recovery-evidence.md)
- [Approved remaining-Major follow-up](follow-up-amendment.md)
- [Remaining-Major implementation evidence](follow-up-evidence.md)
