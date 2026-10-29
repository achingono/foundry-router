# Independent plan review — October 29, 2026

**Verdict: Approved for local implementation.** No Critical or Major plan findings. Production deployment remains subject to the separately reviewed concrete packet and monetary inputs already required by the plan; this verdict is not live acceptance.

Reviewer: independent `credit_plan_review` session, `gpt-6-astra`, separate from the plan-authoring coordinator. The reviewer inspected current git status, all seven plan artifacts, canonical shared-credit operations, the memory/Table settlement and recovery paths, Table serialization/config merges/rollover, admin/metrics boundaries, usage-cost calculation and existing credit/stream/recovery tests. No implementation was modified.

## Reviewed artifacts

- [Design and rollout](index.md)
- [Inputs](inputs.md)
- [Activities](activities.md)
- [Outputs](outputs.md)
- [Exit criteria](exit-criteria.md)
- [Risk register](risk-register.md)
- [Initial evidence](evidence.md)

Approval covers the current two-counter design, optional validated cached-input pricing with full-price admission, and a future scoped memory/one handoff. A change to financial settlement policy, provider scope, counter persistence semantics or rollout authority requires renewed independent review.

Reviewed design SHA-256 (`index.md`): `354dabdf5eae6fbcc0b4a61116dd91bf40264162b7d4d8778fe448cad3194d5b`.

## Implementation review notes

These notes clarify the approved design and should be checked during implementation review:

1. **Suggestion — diagnostic meaning.** Describe the total as cumulative *settlement/recovery credit reductions*, with recovery a subset. Config clamps, reconciliation ceilings/replacements and cycle replenishments are separate balance adjustments and are not represented by these two counters. Neither counter is an authoritative bill, full historical usage total, or independently sufficient to reconstruct balance movement. Legacy Table counters begin at zero when introduced; memory counters reset with the process. Avoid calling them a complete record of every balance change.
2. **Suggestion — Table field preservation and rollout.** Every balance reconstruction must preserve both counters, including admission, both config-merge retry branches, reconciliation, rollover and retained-intent recovery. Existing Table writers use complete replacement entities and would omit new fields, so document a drained all-writer upgrade before relying on these counters in Table mode. This does not require a Table production cut-over.
3. **Suggestion — numeric invariants.** Validate present counter fields as finite, nonnegative numeric values excluding booleans; recovery must not exceed total. Check accumulation before financial mutation/transaction so invalid totals cannot partially apply a debit or persist unreadable state. Tests should also cover actual applied debit when requested charge exceeds remaining credit.
4. **Suggestion — cached-token precedence.** Tests should cover zero cached price, all/partial/no cached input, cache counts beyond explicit input, booleans/floats/negative counts, missing input with total-token fallback, and conflicting Responses/Chat token aliases. Every invalid or ambiguous cache subset must retain ordinary input pricing. Check both nonstreaming and nested terminal SSE usage without changing public bytes or quota token counts.

## Gates assessed

The plan requires one implementation writer, meaningful focused tests followed by full unit/integration coverage of at least 80%, Ruff lint/format, mypy, applicable Azurite and Docker/health checks, documentation/link/secret/status checks and independent contextual deep review. The SonarQube script is absent, correctly recorded as not applicable rather than passed.

The scope retains authenticated diagnostics, shared-credit ownership, conservative missing-usage/recovery settlement, bounded retries and no retry/failover after meaningful SSE output. Canonical shared counters are not added to per-worker OTLP exports; duplicate Table-worker views must not be summed.

Before live changes, establish fs-openclaw allowance and current remaining USD plus exact cached-input rates from operator/provider evidence. Preserve the verified cycle dates and all other account estimates through the planned drained handoff. A provider query with delayed/incomplete costs cannot alone establish a safe fresh balance. Independently review exact image/config pins, barrier/drain evidence and acceptance before deployment. New health/admin acceptance must not be reported as verified inference.
