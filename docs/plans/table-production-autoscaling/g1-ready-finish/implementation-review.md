# G1 ready-finish implementation review

This file preserves the first contextual review and its findings below. The
latest amended-candidate verdict and hashes are in [Final re-review](#final-re-review);
the first review's hashes and check counts are historical and do not describe
the current candidate.

Date: 2026-10-30. Reviewer: independent OpenCode session, separate from the
candidate author. This review covers the local implementation against the
[approved activity plan](activities.md), [plan verdict](plan-review.md),
[finish packet](packet.md), adjacent frozen recovery/continuation helpers, and
the repository's [deep-review prompt](../../../../.agents/prompts/deep-review.prompt.md).

## Initial candidate verdict — superseded

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

The reviewer inspected the source and tests at that revision. Reported
local checks were 44 focused tests passed at 99.04% runner coverage, 3,130
repository tests passed / 21 skipped at 90.46% runtime coverage, Ruff lint and
format passed, and source plus operator Mypy passed. SonarQube is unavailable in
the repository and is recorded as N/A, not a pass. These checks are not live
acceptance evidence.

The sole suggestion was to refresh the packet's stale local-test figures; that
documentation was updated to the results above. No Critical or Major findings
remain from this review. Exact execution approval and a fresh hash-bound private
prepare remain separate gates.

## Final re-review

Date: 2026-10-30. Reviewer: a fresh independent OpenCode session, separate from
the implementation author and prior reviewers.

**No Critical or Major findings remain.** The reviewer confirmed the prior
rolling-topology issue is fixed: `topology()` now compares complete
revision-to-revision templates without stripping `revisionSuffix`; only the
app-to-revision API-view normalization handles the observed null/missing
revision-side suffix. It also confirmed the exact packet instructions require
inspection of revision-only probe values and the runner rejects probe drift
after preparation before ingress or inference.

| Current reviewed file | SHA-256 |
| --- | --- |
| [Runner](../../../../scripts/quality/table_production_acceptance_finish.py) | `a6dc898566616c846000b7a3a1f6df9d52b5d8a8dc127b4308b1353465263231` |
| [Focused tests](../../../../tests/unit/test_table_production_acceptance_finish.py) | `38d2938e6e4c31ea1dc0ee357d86d6a44a856cf1fcd5f1bd99b4e06d9c776413` |

The exact live app/revision field comparison was informed by read-only ARM
queries; the current packet binds the full revision template in its fresh
prepared bytes and rechecks it before cases, settlement, restart, and after
restart. This was code review only: the reviewer did not run tests, access or
review the private prepared packet, call Azure/provider endpoints, mutate Azure,
or grant execution approval.

The current writer-run local checks were 48 focused tests passed at 98.58%
finish-runner coverage, 3,134 full-repository tests passed / 21 skipped at
90.46% runtime coverage, full Ruff lint/format, and source plus operator Mypy.
The final reviewer did not rerun those checks. SonarQube remains N/A because the
script is absent. Fresh private preparation, exact private-packet review and
approval, live inference/restart, and separate restoration remain pending.
