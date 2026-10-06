# Settings identity evidence

**Planned**. Full test failed once; isolated test passed. Inspected id-only cache in both stores
and temporary initial Settings fixture; object ID reuse explains missed changed-config merge.
Templates copied before writing plan. Independent review requested before runtime fix.

Independent minimal-fix design review approved one retained reference/is comparison, complete
sync assignment and reset release. No scope expansion for unsupported in-place config mutation.

**Implemented**. One actual successful Settings reference retained per store, compared with is
under existing lock; assignment remains complete-sync-only and reset releases it. Independent
implementation review passed with no Critical/Major findings.35focused credit/concurrency tests
pass, including changed allowance/cycle under equal membership, reset and failed same-object
retry. Full suite971passed,2Linux-only skips,15deselected,88.49%coverage. No storage schema,
production config or credit-settlement changes. In-place same-object edits remain unsupported.

Actual local Azurite Table SDK verification14passed,974deselected; existing emulator reused
with sandbox network escalation. Docker state-identity image built successfully.
