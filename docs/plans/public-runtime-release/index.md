# Public runtime release

Status: Preparation plan independently reviewed in a separate session before export; candidate verification and final independent review remain required.

Export the reviewed committed runtime and its focused tests onto the existing public baseline. Preserve runtime and Docker build inputs exactly. Include the production workflow guard and generic documentation for optional Azure intake and completion observations. Exclude environment-specific deployment records, financial allocations, resource identities, private operator helpers and their dependent tests.

This preparation does not deploy or publish. Before publication, review every outgoing commit and its ancestry, filenames, messages and complete contents. Before deployment, use the [maintenance procedure](../../operations/production-deployment.md) with environment-specific acceptance evidence retained outside the public repository.

- [Inputs](inputs.md)
- [Activities](activities.md)
- [Outputs](outputs.md)
- [Exit criteria](exit-criteria.md)
- [Risks](risk-register.md)
- [Evidence](evidence.md)
