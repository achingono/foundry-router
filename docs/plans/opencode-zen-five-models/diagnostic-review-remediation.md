**Remaining required fixes — not approved for diagnostic dispatch.**

1. **Major — original manifest is not validated.**  
   [opencode_five_diagnostic.py:169](../../../scripts/quality/opencode_five_diagnostic.py) only compares the identity and ledger’s stored hashes. It never reads/recomputes the original manifest or compares it with the reviewed public manifest digest. Matching incorrect hashes, or a truncated one-entry ledger, can pass. Validate the actual manifest against the reviewed binding, require the complete ledger shape, and verify exactly the original failed slot is consumed. This is an approval invariant that static analysis cannot establish.

2. **Major — timeout during cleanup can retain a completed status.**  
   [opencode_five_diagnostic.py:281](../../../scripts/quality/opencode_five_diagnostic.py) sets `diagnostic_complete` before leaving the HTTPX contexts. If cleanup then times out or raises `HTTPError`, the handler adds an error category but preserves that completed status. Explicitly set `consumed_failed` in the exception handler. This depends on asynchronous cleanup timing.

The identity-encoding/raw-read bound and directory durability fixes resolve their prior Majors. The `.004` debit remains consumed on every outcome, leaving the local estimate `.095982`; processing deadline checks and execution fingerprints are present.

Read-only review completed against the prior report. No edits, inference, private-packet inspection, or subagents.