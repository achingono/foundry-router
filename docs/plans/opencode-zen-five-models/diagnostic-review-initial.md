**Required fixes — not approved for dispatch.** Read-only review completed; no edits, inference, private-packet inspection, or subagents.

1. **Major — 120-second deadline is not enforced.**  
   **File:** [opencode_five_diagnostic.py:153](../../../scripts/quality/opencode_five_diagnostic.py)  
   **Issue/impact:** HTTPX’s 30-second timeout applies to individual operations. Elapsed time is checked only after a body chunk arrives; slow headers, a blocked read, or EOF can exceed the deadline. Parsing and translation have no deadline check.  
   **Why static analysis misses it:** This depends on transport timing semantics.  
   **Fix:** Use an enforceable total deadline covering dispatch, response reading, and processing, with cancellation and a durable failed outcome.

2. **Major — 256 KiB bound applies after decompression.**  
   **File:** [opencode_five_diagnostic.py:165](../../../scripts/quality/opencode_five_diagnostic.py)  
   **Issue/impact:** `iter_bytes()` automatically decompresses responses before the size check. A compressed chunk can allocate substantially more than 256 KiB.  
   **Why static analysis misses it:** The allocation occurs inside HTTPX’s decoder.  
   **Fix:** Request identity encoding, reject unexpected content encoding, and read bounded raw chunks—or implement explicitly bounded decompression.

3. **Major — staging economics and exact execution bindings are incomplete.**  
   **File:** [opencode_five_diagnostic.py:111](../../../scripts/quality/opencode_five_diagnostic.py)  
   **Issue/impact:** Any snapshot balance above `.054` passes; `assert` disappears under optimized Python. The consumed record omits the original failed-slot identity, snapshot hash, reviewed code/profile binding, and actual native-body hash. It therefore cannot establish the authorized amendment’s exact accounting and wire request.  
   **Why static analysis misses it:** These are approval and credit-allocation invariants.  
   **Fix:** Explicitly validate the original stopped-stage identity, finite bounded balance matching the supplied `.099982`, and zero reservations. Bind the snapshot, diagnostic identity/code, low-thinking profile, prices, and generated native-body hash before egress. Permanently retain the `.004` debit on every outcome: remaining estimate **`.095982`**, with no replenishment or production transfer.

4. **Major — consume marker lacks directory durability.**  
   **File:** [opencode_five_diagnostic.py:118](../../../scripts/quality/opencode_five_diagnostic.py)  
   **Issue/impact:** Exclusive creation prevents concurrent execution at the same path, but file `fsync()` alone does not durably commit its directory entry. A crash can lose the marker after dispatch and permit replay.  
   **Why static analysis misses it:** This is a filesystem crash-consistency invariant.  
   **Fix:** Fsync the containing directory before egress; use one fixed diagnostic identity/path and refuse alternate-path replay.

The current request matches the original Flash nonstream slot; the adapter sets low thinking, one candidate, text output, and max512. Retries and redirects are disabled. The sanitizer suppresses free-text values and unknown field names, retaining bounded numeric usage and finish enums. Those controls are sound, but they do not clear the findings above.