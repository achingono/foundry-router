# Phase 03 Routing Hardening

## Companion Documents
- [Inputs](inputs.md)
- [Activities](activities.md)
- [Outputs](outputs.md)
- [Exit Criteria](exit-criteria.md)
- [Risk Register](risk-register.md)
- [Evidence](evidence.md)

## Objective
Harden the implemented Phase 03 routing layer while clarifying its safe response-header contract. Reduce failover branching, preserve selected upstream response metadata, strengthen retry and streaming lifecycle tests, bound pre-output stream waiting, and keep verification evidence current.

## Scope

### In Scope
- Simplify repeated cooldown/failover decision handling.
- Preserve an explicit safe response-header allowlist.
- Add retry timing, same-backend concurrency, streaming cancellation/cleanup, and bounded pre-output tests.
- Bound empty pre-output stream chunks using an explicit timeout and empty-chunk budget aligned with the current HTTP client timeout policy.
- Update Phase 03 verification evidence.

### Out of Scope
- New runtime configuration settings.
- Credit-aware routing, metrics, infrastructure, or Azure integration tests.

## Entry Criteria
- Phase 03 routing implementation and existing unit tests are present.
- The current focused and full unit suites pass.

## Exit Criteria
See [Exit Criteria](exit-criteria.md).

## Roles
- Owner: Implementation agent
- Reviewer: Independent review session
- Approver: Project maintainer
