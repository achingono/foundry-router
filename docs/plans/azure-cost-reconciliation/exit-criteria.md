# Cost reconciliation exit criteria

- [x] Independent plan review clears material findings before runtime edits.
- [ ] Default static behavior retained; opt-in mapping and transport confined and bounded.
- [ ] Billing costs never presented as authoritative balances or applied as replacements.
- [ ] Concurrent debits/inflight preserved; cycle/policy changes reject stale ceilings.
- [ ] Provider outages leave estimates intact and do not prevent reservation maintenance.
- [ ] Focused/full tests, at least 80% coverage, Ruff/mypy, Azurite and Docker pass.
- [ ] Contextual implementation review clears Critical/Major findings; links/diff checked.
- [ ] Evidence, canonical docs and phase commit recorded; live status remains explicit.

Actual Azure read-only acceptance remains a separate gate requiring concrete execution inputs.
