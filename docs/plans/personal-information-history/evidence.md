# History cleanup evidence

## Evidence
- All local reachable objects audited before rewrite. Five screenshot paths are the only historical binary artifact paths.
- Additional historical private home path found in an old planning finding; real account hostname appears in five evidence paths.
- Two distinct author/committer identity combinations found; all identities will be neutralized.
- No provider key or private-key pattern detected in historical reachable blobs.

## Completed local rewrite

- Independent plan review approved. Reviewed ignore/sanitization changes committed with neutral contributor identity before rewriting.
- git-filter-repo rewrote all reachable histories, removed the eight private artifact paths,
  sanitized known project/registry/home-path values in content/messages and neutralized names/emails.
  Filter-repo automatically performed its standard repack/cleanup; final explicit pruning follows verified preservation and scans.
- Verified 3,670 reachable objects, all commit identities, path/ref names and zero known private values.
  Original stash and checkpoint refs included. Restored remote-tracking refs to mapped sanitized
  commits locally after filter-repo's origin removal/ref conversion, without network access.
- Thirteen original artifact/backup SHA256 values verified; all src/tests/scripts/infra files
  match the pre-rewrite tree. No runtime behavior change. Recovery bundle, pending patch,
  audit values and commit mapping stay owner-readable in ignored private storage.
- Local origin URL restored; remote repository has not been fetched or updated and retains its prior history.
- Existing planning evidence describes the earlier index-only stage historically; this phase supersedes its history limitation locally.

- Final stored-object scan covers all 3,670 objects, including unreachable objects: no known sensitive values or personal commit identities remain. The cited original commit is absent. Reflogs expired, explicit pruning completed, and `git fsck --full --no-reflogs` reports no errors or dangling objects.
- Exact original ref set restored; all non-main tips match the filter map, and main contains the mapped previous tip plus the reviewed cleanup commit. No historical refs point to old commits.
- Ruff lint/format pass (829 Python files), affected relative links resolve, and diff whitespace passes.
- Plan JSON policy remains separate: 162 current tracked JSON files include raw evidence and a test-consumed reviewed manifest. This cleanup sanitizes known sensitive values in their full history without deleting all manifests or changing test dependencies.

- Independent final contextual review passed with no Critical/Major findings; all exit gates completed. See [implementation review](implementation-review.md).
