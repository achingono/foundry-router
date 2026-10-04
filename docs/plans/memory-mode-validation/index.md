# Memory-mode Azure validation and baseline deployment

## Status: Implemented

Fix the reproduced memory-mode `InvalidTemplate` storage-account reference failure before refactoring infrastructure contracts. Azure Table deployment and multi-replica runtime validation remain separate gates.

Memory isolation, workspace bootstrap, supported Analytics plan, and removal of the unsupported ACA ports field are implemented. The synthetic memory baseline deployed and passed health/auth/models/admin/metrics checks. Real inference and Table runtime deployment remain unverified.

- [Inputs](inputs.md)
- [Activities](activities.md)
- [Outputs](outputs.md)
- [Exit criteria](exit-criteria.md)
- [Risk register](risk-register.md)
- [Evidence](evidence.md)
