# Signed intake and worker hardening

**Implemented** local hardening; signed continuation remains **Partially implemented** under
its startup gate. This increment is reconciled with remote `45cbb70`. No live inference,
production configuration change or deployment is included.

Offloaded Responses intake acquires one of the existing two work slots before buffering.
Declared oversized bodies fail header checks with 413; saturated requests with unknown body
length return 503 without reading. Slow readers hold capacity until the original intake deadline.
Incoming chunks are checked before copying into the router buffer. Active parser workers retain
capacity after caller cancellation until actual completion.

An owned future hands off worker results and exceptions, avoiding Python 3.14 shield late-error
logging for abandoned work. Completed references are detached so failed jobs release captured
payloads without cyclic GC. Normal failures still propagate to active callers.

Canonical encoding skips redundant parsing only for exact builtin trees within both structural
and value-depth bounds. Subclasses retain strict encoded-output validation. History snapshots
decode only validated canonical bytes and retain no mutable caller children. The external JSON
depth prescan uses the standard decoder's strict string primitive, deletes its temporary result,
and retains final duplicate/nonfinite/depth/node validation. Mixed Unicode temporary allocation
can reach approximately four times input bytes plus Python string overhead.

Independent design and implementation reviews cleared each change with no Critical/Major
findings. Regression coverage includes empty-container depth, malicious subclasses, mutable
snapshot ownership, malformed escapes, large Unicode strings, cancellation/completion races,
late worker failures, delayed submission, slow reads, disconnects and actual SDK signed replay.
The final reconciliation review passed 236 focused tests with two platform skips. Inspector
orphan documentation now describes eight as the rejection threshold; already admitted work can
transfer additional children before subsequent admission fails closed.

Validation: full local suite 1,509 passed, three platform skips, 15 Docker/Azurite deselected,
88.86% coverage; 75 focused tests passed on Linux Python 3.12; Ruff, formatting, mypy and runtime
Docker build/health passed. The conditional Sonar script is absent. Existing Azurite evidence
was not rerun for this feature-local increment.

Remaining gates:

1. Rerun signed resource measurements against the reconciled runtime, then resolve failures
   under the unchanged 128 MiB incremental RSS and 50 ms event-loop limits. Prior measurements
   failed and predate remote cleanup fixes.
2. Complete signed PDF/WAV/AVI and jointly feasible state/media resource, cancellation,
   delivery and redaction checks; finish larger-image/lossy-WebP contracts and accounting.
3. Approve exact model/capability/free-tier cases and finish guarded live execution with the
   existing 20 requests / 20,000 tokens per project and zero paid-spend authorization. The
   committed live catalog is a synthetic offline fixture, not provider compatibility evidence.
4. Update the full requirement audit from passing evidence before enabling gated capabilities.
   Production cut-over remains a separate decision; production stays memory-backed/one replica.
