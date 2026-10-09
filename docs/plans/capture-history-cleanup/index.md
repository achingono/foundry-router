# Unused capture history cleanup

## Status: Partially implemented

## Objective
User authorized removal from commit history of all captures not used by tests. Audit current and
historical non-Markdown artifacts under `docs/plans/`, identify direct/indirect test reads, preserve
only required test inputs, and remove all other JSON/TXT capture paths from every local Git ref.

## Sequence
1. Inspect static test/script dependencies and trace actual file reads during the full offline
   test suite. Keep reviewed manifest/catalog and historical result/ledger prerequisites tests read.
2. Independently review this plan and the explicit keep list before implementation.
3. Preserve local artifact bytes and hashes, refs and recovery bundle in owner-only ignored
   `private/capture-history-cleanup/`. Add ignore rules for plan JSON/TXT with exact tested exceptions.
4. Untrack unused captures while retaining them locally; replace Markdown links with explicitly
   local-only paths and document fresh-clone operator requirements. Retain source scripts and all
   required test artifacts at their existing locations; no runtime/test behavior changes.
5. Verify focused and full offline tests/coverage in a clean checkout without ignored captures,
   lint/format/type checks and documentation links. Docker build is not applicable to a docs/index
   change; SonarQube script absent. Check runtime/infra/script/test bytes unchanged.
6. Commit the cleanup, rewrite every local history/ref removing unused historical artifact paths,
   restore origin/ref topology locally, verify all stored objects/refs and local preserved hashes.
7. Independently review, prune unreachable objects and record outcomes with neutral commit identity.

## Boundaries
This task removes capture artifacts, not Markdown plans or source code. A test merely mentioning
an output path does not require retaining its actual capture. Trace reads and inspect indirect
prerequisite files before selecting exceptions. Prior/private original artifacts remain ignored.
No remote network updates; previously published history remains until coordinated updates.

## Companion documents
- [Inputs](inputs.md)
- [Activities](activities.md)
- [Outputs](outputs.md)
- [Exit criteria](exit-criteria.md)
- [Risks](risk-register.md)
- [Evidence](evidence.md)
