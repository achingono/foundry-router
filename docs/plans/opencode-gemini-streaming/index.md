# Gemini streaming resolution (streaming-first gate)

Status: **Planned**. Independent [re-review](plan-rereview.md) approves local implementation; all three original Majors are resolved. The [allocation amendment](allocation-amendment.md) is independently [approved](allocation-review.md) with no Critical/Major findings. Paid diagnostic, staging and production execution each require their concrete packet gates below; no live spend until those gates pass.

## Companion Documents
- [Inputs](inputs.md)
- [Activities](activities.md)
- [Outputs](outputs.md)
- [Exit Criteria](exit-criteria.md)
- [Risk Register](risk-register.md)
- [Evidence](evidence.md)
- [Independent review](independent-plan-review.md)
- [Allocation amendment](allocation-amendment.md)
- [Allocation review](allocation-review.md)

## Objective

Establish the native Gemini SSE incompatibility that caused the Vertex-time Flash stream 502 before public output, then make the smallest bounded adapter correction and qualify streaming for both Gemini Flash and Argon. Flash diagnosis is an intermediate milestone, not production qualification. Production remains blocked under the operator's streaming-first choice until both exact models pass staging and the reviewed production handoff is ready.

## Scope

### In Scope
- One direct, bounded Flash native streaming structural diagnostic, funded solely from the stopped isolated staging allocation. The prior nonstream diagnostic is a reference pattern, not a reusable execution identity or approval.
- Smallest `google_native.py` streaming-envelope correction if diagnostic proves the cause, plus focused/full tests, lint/format/types, new Linux/amd64 image, independent code/packet review.
- Narrow acceptance-harness and configuration changes: one new recognized eighteen-slot identity, nine cases per environment, with both Gemini pools streaming-enabled. This supersedes the proposed eight-case gate and the prior Gemini-nonstream acceptance policy only for the new identity.
- A reviewed production release packet requiring the same nine exact-model cases, with subsequent execution under the inherited five-model drain/handoff procedure. Sonnet remains nonstream-only; Grok/Muse retain both modes.

### Out of Scope
- Production mutation during diagnosis or staging; execution of the operator-owned drain; auth rotation, pricing changes, Sonnet/Grok/Muse runtime behavior changes, Table cut-over, embeddings, cost reconciliation.
- Automatic extra diagnostics, retries, model substitution or replay. An Argon failure requires a separate reviewed amendment; its streaming acceptance is mandatory regardless of whether a separate diagnostic is needed.

## Entry Criteria
- ca6 seven-case staging record preserved (`sha256:180b9d9efc0f5ccb01528ac8178ac28babae2470e991cbd34f212a22cad6d27e`); writer stopped, zero reservations; no prior ledger replay.
- Retrieve and validate actual ca6 stopped snapshot/remaining and stopped-writer proof before diagnostic spend; unresolved artifacts block dispatch, not offline implementation.
- Independent plan review approves this scope with no Critical/Major findings.

## Exit Criteria
See `exit-criteria.md` and the concrete contracts in [activities](activities.md). Production remains **Planned**, memory-backed with one worker and max one replica. Updated policies, all nine staging passes, stopped staging and inherited fresh handoff gates are prerequisites to promotion; all nine production passes precede restoration of original ingress.

## Roles
- Owner: coordinator
- Reviewer: independent session/model (did not author plan or prior runtime)
- Approver: operator

## References
- [Five-model rollout](../opencode-zen-five-models/index.md), [evidence](../opencode-zen-five-models/evidence.md)
- [Nonstream deployment amendment](../opencode-zen-five-models/nonstream-deployment-amendment.md)
- [Nullable amendment](../opencode-zen-five-models/anthropic-nullable-amendment.md)
- Streaming implementation: `src/foundry_router/api/adapters/google_native.py:690-748`
- Prior diagnostic: `scripts/quality/opencode_five_diagnostic.py`
