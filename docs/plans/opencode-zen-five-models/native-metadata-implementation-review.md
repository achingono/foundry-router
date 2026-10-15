**Approved for the nine replacement isolated staging calls, once. Production transition remains blocked by two Major operational findings.**

The public packet exactly matches the runner-generated manifest: replacement identity `opencode-zen-five-20261013-model-status`, ca4 Linux/amd64 digest `sha256:5d88b363deae42e1d24179b8fd9f38f9bf7b981f37d6daab4dbf525c19fa1a6c`, staging **0.095982 USD**, production **9.90 USD**.

No contextual blocker found in shared `_validate_envelope`, nonstream/content/usage-only stream coverage, or fixed replacement identity/replay rejection. The Google change does not affect the Anthropic adapter. `modelStatus` remains a plausible cause, not a confirmed diagnosis.

1. **Major — stopped-writer proof fails open**
   - **File:** `/private/tmp/opencode_five_live.py`, `/private/tmp/opencode-five-promote2.py`.
   - **Issue:** `.get('replicas', 0)` treats missing replica evidence as zero. Inactive revision metadata alone does not establish that terminating writers have disappeared.
   - **Why static analysis misses it:** This depends on control-plane response semantics and asynchronous shutdown.
   - **Impact:** Promotion can proceed without proving zero old writers.
   - **Fix:** Explicitly enumerate replicas for every old revision; require successful, empty results and reject absent or ambiguous evidence. Repeat immediately before promotion.

2. **Major — barrier snapshot binding is not enforced downstream**
   - **File:** `/private/tmp/opencode-five-promote2.py`.
   - **Issue:** Preparation reads `final-drained-snapshot.json` without checking its fingerprint against `barrier-proven.json`. Its policy comparison deliberately excludes inherited balances.
   - **Why static analysis misses it:** Each hash operation is valid; the missing relationship spans operational phases.
   - **Impact:** A stale or substituted snapshot with identical policy can supply incorrect inherited seeds and then receive a fresh immutable handoff.
   - **Fix:** Verify the barrier-recorded snapshot hash and drained/process-continuity evidence before deriving seeds; carry that verified binding through the handoff and recheck before promotion.

Production remains conditional on nine staging passes, stopped staging, proven admission barrier/no bypass, final drained snapshot, stopped writers, and a fresh immutable handoff binding **all inherited seeds, fixed OpenCode 9.90, exact pinned payload/configuration, image and manifest**.

Full-suite log confirms **2,678 passed, 3 skipped, 19 deselected**. Focused results, coverage and lint/type outcomes are supplied evidence; Sonar script is absent. No edits, inference, subagents or referenced private-data reads were performed.