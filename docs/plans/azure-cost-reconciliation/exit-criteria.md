# Cost reconciliation exit criteria

- [x] Independent plan review clears material findings before runtime edits.
- [x] Default static behavior retained; opt-in mapping and transport confined and bounded.
- [x] Billing costs never presented as authoritative balances or applied as replacements.
- [x] Concurrent debits/inflight preserved; cycle/policy changes reject stale ceilings.
- [x] Provider outages leave estimates intact and do not prevent reservation maintenance.
- [x] Focused/full tests, at least 80% coverage, Ruff/mypy, Azurite and Docker pass.
- [x] Contextual implementation review clears Critical/Major findings; links/diff checked.
- [x] Evidence, canonical docs and phase commit recorded; live status remains explicit.

Actual Azure read-only acceptance remains a separate gate requiring concrete execution inputs.
