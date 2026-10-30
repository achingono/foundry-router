# G1 ready-finish implementation review

Date: 2026-10-30. Reviewer: independent OpenCode session, separate from the
candidate author. This review covers the local implementation against the
[approved activity plan](activities.md), [plan verdict](plan-review.md),
[finish packet](packet.md), adjacent frozen recovery/continuation helpers, and
the repository's [deep-review prompt](../../../../.agents/prompts/deep-review.prompt.md).

## Verdict

**No Critical or Major findings.** This is a contextual code review only; it is
not Azure/live acceptance, an exact packet review, or execution approval. No
Azure mutation, provider request, restart, or production operation was performed
for this review.

## Reviewed candidate

| File | SHA-256 |
| --- | --- |
| [Runner](../../../../scripts/quality/table_production_acceptance_finish.py) | `799cc9e96019ea659037ba7f998e23631394872958c2ef5fd004734e83d7774b` |
| [Focused tests](../../../../tests/unit/test_table_production_acceptance_finish.py) | `b231d3146f9d1fb1e9202016521d257dc1a98be4c5090c916e9520cec0a7f8a3` |

## Previously reported Major findings — closed

1. **Prepared-packet approval binding:** `apply()` acquires the finish execution
   lock before reading the private packet, hashes the bytes read once, checks
   approval against that hash, executes from the bound in-memory packet, and
   verifies the on-disk bytes again before consuming the global guard or
   mutating ingress. A regression test attempts packet replacement and proves
   refusal before mutation.
2. **Restart deadline:** one 180-second budget phase begins before the restart
   operation. The existing budget-aware Azure CLI, all-revision inventory,
   snapshots, readiness wait, and result writes inherit that phase deadline;
   normal cleanup headroom remains reserved.
3. **Response and clean-EOF evidence:** each accepted case receipt binds the
   HTTP response and terminal response/usage files. Streaming cases additionally
   bind the terminal event and a clean-EOF receipt created only after the
   dispatch helper validates completion and the final SSE boundary. The final
   result hashes each receipt; tests verify that later observation drift is
   detected.

## Verification context

The reviewer inspected the current source and tests after the fixes. Reported
local checks were 44 focused tests passed at 99.04% runner coverage, 3,130
repository tests passed / 21 skipped at 90.46% runtime coverage, Ruff lint and
format passed, and source plus operator Mypy passed. SonarQube is unavailable in
the repository and is recorded as N/A, not a pass. These checks are not live
acceptance evidence.

The sole suggestion was to refresh the packet's stale local-test figures; that
documentation was updated to the results above. No Critical or Major findings
remain from this review. Exact execution approval and a fresh hash-bound private
prepare remain separate gates.
