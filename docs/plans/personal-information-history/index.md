# Personal information history cleanup

## Status: Implemented

## Objective and scope
User explicitly authorized amending previous commits to remove personal and sensitive information.
Rewrite every local branch/tag/remote-tracking history: remove the eight private quota artifacts,
replace discovered real project/registry identifiers and private home paths in blobs and commit
messages, and anonymize author/committer names and emails. Preserve public role IDs, synthetic
fixtures and examples. Audit all reachable historical blobs, including renamed paths, before rewriting.

## Sequence
1. Audit refs, historical objects and identities. Obtain independent plan review.
2. Preserve current private artifacts and create an ignored local recovery bundle; never publish it.
3. Commit the pending reviewed ignore/sanitization change with neutral contributor identity.
4. Use git-filter-repo to remove private paths and replace known identifiers/private paths in
   all refs, messages and identities. Preserve origin configuration locally and avoid remote writes.
5. Scan every reachable blob/commit and refs for known identifiers and removed paths. Confirm
   private file hashes, clean working tree, ignored originals and unchanged runtime tree.
6. Record commit mapping and review results without sensitive values. Expire reflogs and prune
   unreachable Git objects after successful verification; local recovery bundle remains ignored.
7. Independently review the result. Explain old hashes change and remote copies remain until
   separately published with coordinated force updates.

## Boundaries
This authorization covers local history rewriting. No remote push is included. Sensitive recovery
material remains only in ignored private storage and is explicitly excluded from Docker context.
Runtime tests/type checks/build are unnecessary if runtime tree is byte-identical. Run Ruff/link/
whitespace checks for documentation changes. SonarQube script absent.

## Companion documents
- [Inputs](inputs.md)
- [Activities](activities.md)
- [Outputs](outputs.md)
- [Exit criteria](exit-criteria.md)
- [Risks](risk-register.md)
- [Evidence](evidence.md)
