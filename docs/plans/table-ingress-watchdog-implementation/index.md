# Isolated Ingress Watchdog Implementation Plan

**Status: Partially implemented; local-only.** Independent review
conditionally approved the plan and passed the suspension-guarantee amendment
with no material Critical/Major findings. The guarantee is explicitly
limited to a running gateway host; total suspension/loss invalidates the session
and has no finite socket-closure bound. Local protocol primitives and focused
tests are in progress. Resume ordering, end-to-end process wiring and all Azure,
budget and exact G1 packet gates remain open.

## Objective

Implement and locally verify the independently reviewed [watchdog design](../table-ingress-watchdog-20261030/design.md): an independently hosted, default-deny gateway that fences four fresh isolated Table G1 cases with an expiring lease, durable one-use records, independent financial verification, and attributable pre/post-restart ACA denial proof. The existing shared app and its remaining case-3 slot are ineligible.

## Companion Documents

- [Inputs](inputs.md)
- [Implementation activities](activities.md)
- [Wire and state protocol](protocol.md)
- [Outputs](outputs.md)
- [Exit criteria](exit-criteria.md)
- [Risk register](risk-register.md)
- [Evidence](evidence.md)
- [Independent plan review](plan-review.md)

## Scope and boundaries

- Build a standalone operator-only gateway, supervisor, verifier and fresh G1 harness; keep them outside `src/foundry_router/`. Do not modify the existing resume runner or its user changes.
- Implement mock-backed local tests first; Azure resources and paid cases are separate future gates. No production rollout or current shared-app mutation is included.
- Select a dedicated internal ACA environment/VNet and VM gateway, with no shared-environment fallback. The exact resource plan, identity roles, cost, region and finite what-if must be separately bound and reviewed before any Azure mutation.
- Four cases require a fresh exact packet, distinct slots and remaining aggregate liability/attempt accounting. Do not transfer or reset the prior slot, histories, reservations or budget.
- Treat estimated debits as local estimates, not authoritative Azure balances. Never log prompts, outputs, authentication material or unredacted diagnostic records.

## Work ordering

1. Independent review of this concrete plan and the narrowed suspension guarantee; resolve all Critical/Major findings before implementation. **Complete:** plan amendment passed review; total host suspension has no finite close bound and invalidates the session.
2. Build and test the local, default-closed gateway/supervisor/verifier and fresh G1 harness as specified in [activities](activities.md) and [protocol](protocol.md).
3. Independently review implementation, complete applicable verification and resolve findings. A local pass is not Azure evidence.
4. Separately prepare and independently review the Azure what-if, identities, costs and disposable feasibility packet; perform only the approved non-paid verification. Block if any isolation, time, WORM, diagnostics or attempt-limit assumption fails.
5. Prepare a fresh exact four-case G1 packet with independently verified budget and signatures. Execute only after its separate independent approval and all preceding gates pass.

Resource provisioning, clock confidence, diagnostics, privilege separation and
financial evidence remain feasibility gates, not established facts. This local
implementation does not authorize or perform Azure mutation or paid requests.
