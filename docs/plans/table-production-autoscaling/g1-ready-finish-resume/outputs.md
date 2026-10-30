# G1 resume Outputs

## Mandatory Outputs

| Output | Description | Format |
| --- | --- | --- |
| Read-only case-2 reconciliation | Hash-bound HTTP/usage, configured-price debit, same-process canonical settlement and zero-reservation proof | Private JSON only |
| Continuation runner and tests | Single-use case-3 tail, no deployment/resource path, exact DENY-on-failure handling | Python plus focused tests |
| Resume/DENY consumption journals | Global continuation identity precedes execution-time checks; the secondary final-DENY marker precedes its sole PATCH, with one DENY attempt still required if that journal write fails; fsync-backed records have ≤15s budget bounds | Append-only private JSON |
| Independent implementation review | Verdict, findings/resolution, exact source/test hashes | Markdown |
| Exact continuation packet and approval | Current live state, hashes, ownership, one original unused slot, cost bound and exact mutations | Private JSON only |
| Final G1 result chain | Four case receipts, case-2 reconciliation link, sanitized per-revision worker-topology summary, restart evidence and original e/a/D/finish/resume provenance | Append-only private JSON |

## Optional Outputs

- None.

## Output Quality Checklist

- [ ] Every artifact is exclusive-create, owner-only, hash-bound, and append-only.
- [ ] No credentials, prompts, model outputs, or unredacted cloud IDs are committed.
- [ ] Any unknown dispatch retains its full original reserve and blocks later calls.
- [ ] Result claims distinguish local, synthetic, read-only reconciliation, and live acceptance.
