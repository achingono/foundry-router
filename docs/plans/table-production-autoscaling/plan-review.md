# Independent phased plan review

Date: 2026-10-30. Reviewer: independent GPT 6 Astra session; not the plan author.

## Verdict

**Phase 0 approved. Phase 1 design approved conditionally: resolve M1 in the exact isolated execution packet before mutation.** Read-only discovery, image/source binding, helper preparation and local verification may proceed now. Plan approval does not approve a deployment, restart or paid call.

**Phases 2–3 are an acceptable staged migration plan**, subject to G1 and independently approved concrete migration/acceptance packets. Production Table/one is a valid completed intermediate outcome. Counter seeding, coverage selection and fresh four-account reconciliation must be resolved before their dependent actions, not before all planning can proceed.

**Phases 4–6 remain Planned.** Payload limits, resource architecture, provider-correct shared admission and metrics decisions gate their own implementation/scale-out. They do not block safe Table/one migration. Other-provider behavior changes and paid calls remain out of scope; whole-app scaling nevertheless requires evidence that preserved providers remain safe.

No Critical findings. One Major packet-level requirement; suggestions below minimize scope.

## Review basis

Read all six plan documents, repository instructions, the contextual deep-review prompt, canonical operations/shared-credit/testing guidance, historical Table real-inference and metadata evidence, the deployed pricing packet, and relevant verifier tests. Inspected local `git status`; existing dirty source/tests/docs are user work. This reviewer performed no Azure commands, inference, tests, builds or source edits. Sonar is reported absent, not passed; this is contextual plan review, not a claim that the prompt's prior-scan premise holds.

Coordinator-supplied fresh discovery reports the existing isolated Table app ready with the older corrected `78c5…` image, compatible candidate credit/health tables in hardened shared storage, and production on immutable `36d453…`. It also reports source/image agreement, 2,887 passed/21 skipped/90.46% coverage, Ruff/mypy passing, Docker available and no production-identity Table grants. These are handoff inputs, not independently rerun results. Bind full identities/hashes privately and attach actual verification evidence to the packets.

## Major

### M1 — Prevent mixed-version isolated Table writers during image replacement

- **File/Module:** [activities.md](activities.md), Phase 1 steps 4–9; old/new isolated revisions sharing historical Table rows.
- **The Issue:** Phase 1 requires quiet compatible tables and one worker/replica but does not explicitly prohibit overlap between old and new revisions during the image update. The old isolated image predates deployed ledger-counter support. Single-replica configuration and a quiet snapshot alone do not prove that an old background writer has stopped.
- **Why Static Analysis Missed It:** This depends on deployment sequencing and the persisted schema behavior of two different releases.
- **Impact:** An older replacement write can discard newer debit/recovery fields, invalidating counter and persistence acceptance. An overlapping admission can also invalidate the test budget/baseline.
- **Recommended Fix:** The exact G1 packet must fence isolated intake, prove drainage/quietness, stop the old revision and verify absence of its workers/background writers before starting the current immutable image against reused rows. Retain historical balances, reservations and ledger bytes; do not reset rows. Recheck clean state and establish the explicit counter baseline before the first paid call. Capture zero old writers and the sole successor as acceptance evidence. This is an operational packet correction, not a request for runtime code or new infrastructure. Independent packet approval must explicitly close M1 before mutation.

## Suggestions

### S1 — Reuse the deployed production image and existing isolated state

- **File/Module:** [activities.md](activities.md), steps 3–5; [risk-register.md](risk-register.md), D1/D2.
- **The Issue:** The plan permits reuse but also lists generic candidate build requirements that could be interpreted as requiring a new release for G1.
- **Why Static Analysis Missed It:** Release provenance and the necessity of a build are workflow decisions.
- **Impact:** An unnecessary rebuild expands review/deployment scope without addressing the remaining real nonstream/restart gap.
- **Recommended Fix:** Prefer the verified, deployed production immutable digest unchanged for G1. Bind current source and existing build/runtime evidence; record applicable fresh checks and explicit exclusions. Rebuild only if a concrete mismatch or required runtime change is found. Reuse historical isolated tables when compatible and quiet; new tables require a demonstrated incompatibility. Production's missing scoped grants belong in its later exact migration packet, not in an unrelated resource expansion.

### S2 — Keep historical synthetic allocations separate from new liability

- **File/Module:** [activities.md](activities.md), steps 5–8; [risk-register.md](risk-register.md), D4.
- **The Issue:** Historical isolated rows used USD 100 allocations and synthetic USD 10/30 pricing. Those values are test state, not an available provider wallet or fresh spending authorization.
- **Why Static Analysis Missed It:** Cross-application allocation ownership is external to the local ledger implementation.
- **Impact:** Treating historical balances as spendable funds would duplicate production liability despite a small call budget.
- **Recommended Fix:** Preserve compatible rows as-is and compare new debit deltas against the pinned test pricing. The packet must separately identify how each new paid slot's conservative liability is reserved outside production's concurrently spendable allocation. Record the mechanism before calls; a second ledger naming the same funds is insufficient. Keep the aggregate USD 1/16 attempts/128 text-output/zero-retry bounds and retain ambiguous reservations. Synthetic debit agreement proves accounting behavior, not actual Azure pricing or balances.

### S3 — Close migration with bounded representative coverage

- **File/Module:** [activities.md](activities.md), Phases 1–3; [exit-criteria.md](exit-criteria.md), G1/G2.
- **The Issue:** Later operation matrices could be mistaken for mandatory exhaustive paid acceptance before migration.
- **Why Static Analysis Missed It:** This is the interpretation of staged acceptance scope.
- **Impact:** Requiring every model/provider would unnecessarily consume the bounded budget and delay persistence migration.
- **Recommended Fix:** Retain the four isolated cases and restart gate. Select exact available models likely to complete within 128 output tokens; do not increase limits or replay on failure. Allocate remaining slots explicitly across production and later two-worker checks. Reviewer-approved representative production Azure coverage and honest exclusions are sufficient for G2; Anthropic/MAI/embeddings coverage need not exhaust the model roster. If mandatory cases cannot fit, amend the packet/scope before calls. Use the already-permitted new counter-lifetime baseline if totals cannot be seeded, preserving fresh conservative balances and never claiming cumulative historical continuity.

## Required handoff

1. Continue Phase 0 and prepare the smallest G1 packet using existing resources and the unchanged production image.
2. Resolve M1 and concrete identity/configuration, row compatibility, disjoint liability, four-case budget, helper invariants and restart bindings in that packet; obtain independent approval before any mutation or call.
3. On G1 success, prepare the four-account production Table/one handoff and fresh-state recovery packet. Keep all later payload/scale decisions phase-local.

Only `plan-review.md` was authored by this reviewer. No execution gate is marked passed by this review.
