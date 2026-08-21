# Phase 04 Credit Scheduling Hardening

## Companion Documents
- [Inputs](inputs.md)
- [Activities](activities.md)
- [Outputs](outputs.md)
- [Exit Criteria](exit-criteria.md)
- [Risk Register](risk-register.md)
- [Evidence](evidence.md)

## Objective
Harden the credit estimation, reservation lifecycle, and streaming cost reconciliation introduced in Phase 04. Defend against unbounded SSE chunk accumulation buffers during streaming passes, enforce strict boundary conditions in usage JSON extraction, and guarantee zero reservation leaks across edge-case client disconnects and cascaded failover paths.

## Scope

### In Scope
- Defend streaming SSE event accumulation with an explicit upper buffer bound (`MAX_SSE_EVENT_BUFFER_BYTES = 128 * 1024`).
- Verify and harden in-flight reservation lifecycle under unexpected client cancellation, transport disconnection, and secondary failovers.
- Test and bound terminal usage parsing across streaming protocols (e.g. OpenAI `stream_options.include_usage`).
- Verify non-2xx zero-charge invariants across all status codes (400, 401, 403, 404, 422, 500, 502, 503).
- Maintain dedicated unit coverage for `src/foundry_router/credit.py` above 90%.
- Document operational characteristics of local conservative credit reservations.

### Out of Scope
- External Azure Cost Management billing synchronization (scheduled for Phase 05).
- Redis or distributed state persistence (scheduled for Phase 06).
- Infrastructure deployment (scheduled for Phase 07).

## Entry Criteria
- Phase 04 credit estimation and in-memory reservation store implemented and tested.
- Review findings in `docs/plans/phase-04-credit-scheduling/review.md` implemented.
- Base unit and integration test suite passing with >= 80% coverage.

## Exit Criteria
See [Exit Criteria](exit-criteria.md).

## Roles
- Owner: Implementation agent
- Reviewer: Independent review session
- Approver: Project maintainer
