# Incremental Bicep module extraction

## Status: Implemented

Extract observability and runtime identity from the verified typed root. Preserve the flat deployment API, resource names/API versions/settings, role GUID inputs and single-replica synthetic baseline. Container Apps environment remains in the root and reads workspace keys directly; credentials must not cross public outputs.

Identity and observability module extraction has passed semantic ARM review, Azure memory/Table template validation, synthetic redeployment and smoke checks. Real inference and deployed Table runtime remain unverified.

- [Inputs](inputs.md)
- [Activities](activities.md)
- [Outputs](outputs.md)
- [Exit criteria](exit-criteria.md)
- [Risk register](risk-register.md)
- [Evidence](evidence.md)
