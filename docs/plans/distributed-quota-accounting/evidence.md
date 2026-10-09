# Quota evidence

**Implemented** locally, 2026-10-08. Planning history: Six planning templates copied before drafting. Inspected
RateLimitStore, memory accounting, Table CAS client, startup/readiness, routing sync and
admission/settlement call sites. Runtime edits started only after independent plan clearance.

Independent review identified Major gaps in midnight quota accounting, logical-ID reuse
across 429 attempts and the UTF-16 property bound. The plan now blocks midnight clock
uncertainty, carries a separate quota ID for every admitted candidate, and bounds the exact
Edm.String UTF-16 storage bytes. Re-review also tightened retention to ≤3,600 seconds and
made drained fingerprint-transition CAS predicates explicit. Final re-review cleared implementation with no remaining Critical/Major issues.
Admission, finalization, release and initialization lost acknowledgements remain explicit
implementation-review cases; no runtime or live verification is claimed yet.

## Implementation verification

**Implemented** locally, 2026-10-08. Final full suite: 1,693 passed, three platform skips,
17 Docker/Azurite deselections; overall coverage 89.51%, quota store 89.39%. Ruff clean,
597 files formatted and strict mypy passed for 66 source files. Conditional SonarQube script
is absent. Final Docker build passed; Python 3.12.15 network-disabled app/compatible decoder smoke passed. Relative links resolved in 20 Markdown files; final whitespace/status/redaction diff review passed.

- [Unit lifecycle tests](../../../tests/unit/test_table_quota.py): 20 passed, including
  simultaneous writers, restart, same-ID rejection, cross-writer settlement, lost
  acknowledgements, policy change, conservative expiry, Pacific midnight/DST, regression,
  ETag/storage bounds, 4,100 cross-writer/expiry lifecycles, Azure dispatch cancellation and
  post-admission exclusion cancellation/intake timeout, configuration and factory wiring.
- [Actual API tests](../../../tests/integration/test_table_quota_integration.py): four passed;
  same-group 429 fallback retains two distinct attempts for normal and streaming Responses,
  quota errors return sanitized 503 with no backend dispatch, including lost admission ack.
  Same-group fallback is explicitly protected emergency policy; normal shared cooldown remains.
- [Real local Azurite tests](../../../tests/integration/test_azurite_quota.py): two passed,
  plus 14 unchanged distributed-state cases. Independent clients verify atomic caps,
  restart/settlement and near-boundary Unicode UTF-16 property size. These are emulator tests,
  not Azure deployment or live provider evidence.
- Existing cancellation regression updated: possible dispatch now settles the full estimate.
  Failed credit settlement preserves a single quota finalization; no free release follows.
- [Independent contextual review](implementation-review.md): findings fixed, no remaining
  Critical/Major design issues; final lifecycle fixture correction passed locally.

Production settings are unchanged. Table quota is opt-in, requires full per-group limits,
separate identity-accessible table, age ≤3,600s and synchronized-host rollout assumptions.
