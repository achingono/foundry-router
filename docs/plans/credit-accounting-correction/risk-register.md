# Credit accounting correction risks

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Duplicate debit/counter updates on retry or lost acknowledgement | Financial corruption/misleading metrics | Update debit counters atomically with financial transaction and preserve idempotent reservation ownership |
| Legacy Table rows/counter loss on reconstructing balances | Diagnostic corruption | Missing-only defaults; reject invalid values; preserve fields on all rebuild/merge/rollover/reconcile paths |
| Incorrect cached subset/price | Underestimated local cost | Validate explicit bounded counts and rate <= normal input; malformed cache detail receives no discount |
| Shared counters summed across Table workers | Duplicate monitoring totals | Canonical-account diagnostics; document nonadditive worker views and no automatic OTLP export |
| Memory restart/stale seeds or concurrent writers | Replenishment/credit loss | Final drained readable snapshots, stopped old writers, pinned coherent config; no stale rollback |
| Missing allowance/pricing facts | Unsafe credit enablement | Required operator/provider inputs before dependent live changes |
