# Capture cleanup evidence

## Evidence
- Current tree clean. Static inspection identifies manifest/catalog and historical prerequisite inputs read by tests.
- Full offline suite file-read tracing initiated before removal.

- Initial full offline suite passed: 2,112 passed, 3 skipped, 19 deselected; coverage 89.89%. Read tracing plus static subprocess/default inspection verifies eleven test inputs.
- Historical blob inventory includes 154 unused artifact paths; 153 currently tracked captures untracked with disk preservation. An old lock capture is included in historical removal.

- Eleven retained artifacts match actual full-suite reads, including subprocess catalog dependency.
- No introduced broken relative links; 142 affected link targets checked against removed capture paths.
- Ignore exceptions checked with `--no-index`, all 153 local-original hashes preserved, no tracked ignored files.
- Ruff lint/format and strict mypy pass. No runtime/test/script/infra changes; Docker build not applicable. SonarQube script absent.

- Final history inventory walks every commit tree to include equal-content blobs at multiple paths; three duplicate-content diagnostic markers bring final totals to 153 current removals and 154 historical paths (including one old lock). All local hashes captured.

- Tracked-only checkout contains exactly eleven plan JSON inputs and no removed captures. All 2,112 tests passed (3 skipped, 19 deselected). Its initial coverage report used editable-install imports from the original checkout and was invalid; rerun pins isolated src/root imports for accurate coverage.
- Independent staged review identified three remaining marker links and duplicate-content historical paths; both corrected. Full commit-tree enumeration avoids object-path deduplication, covers all 154 unused historical paths and all 153 local original hashes.

- Isolated checkout with local-source PYTHONPATH passed: 2,112 passed, 3 skipped, 19 deselected; coverage 89.89%. Exactly eleven plan JSON files available, no unused captures. Independent staged review approved all corrected findings.

## Completed local rewrite

- Neutral-identity cleanup committed, then git-filter-repo removed all 154 unused historical paths
  across local branches, remote-tracking refs, stash and checkpoint refs. Eleven test-used artifacts remain.
- Filter-repo composed maps with the prior privacy rewrite; original ref topology restored through
  the composed mapping. Main includes the mapped prior tip plus cleanup; all other ref tips map exactly.
- Verified all 177 reachable commit trees contain only the eleven allowed non-Markdown plan inputs.
  All 1,470 stored trees checked for removed artifact names. All 153 local capture hashes,
  eleven retained input hashes and 256 source/test/script/infra hashes remain unchanged.
- Local captures ignored, no tracked ignored files, clean tree after rewrite. Reflogs expired,
  unused objects pruned; `git fsck --full --no-reflogs` passed without errors/dangling objects.
- No remote fetch/push. Remote repository and others' clones retain their previous histories.
  Recovery bundle remains owner-only in ignored private storage and must never be published.

- Independent final history review approved with no Critical/Major findings; all exit criteria completed.
