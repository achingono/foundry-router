# Per-group reserve policy amendment (draft — pending independent review)

Date: 2026-10-12. Status: **Proposed; no code changed.**
Single-endpoint constraint (operator tooling addresses one endpoint) rules out
a separate Zen production app, so Zen and the retained Azure accounts must share
one instance. App-wide reserves cannot fit both: USD 10 locks the USD 10 Zen
group as `PROTECTED`; USD 0.05 lowers the floor under the USD 210 Azure groups.

## Proposal (group-level, per operator correction)

- New optional group-keyed policy map, e.g. `FOUNDRY_CREDIT_GROUP_RESERVES_JSON`:
  `{ "<credit_group>": {"min_credit_reserve_usd": float, "min_credit_reserve_percent": float} }`.
  Groups absent from the map inherit app-wide settings. One policy per balance
  by construction, so no cross-backend conflict rule is needed.
- Settings validation (fail-closed): finite non-negative values, percent at most
  100, keys restricted to configured credit groups — unknown-group keys refuse
  at startup.
- One shared resolver (`Settings.resolve_reserve_policy(credit_group)`); call
  sites in `routing/__init__.py`, `api/routes/admin.py`, `api/google_sealing.py`
  resolve backend to group via existing aliases, then policy. `credit.py` core
  unchanged.
- Template: one non-secret parameter/env binding for the JSON map (same pattern
  as model aliases). Production config intent: Zen group `0.05`/`5.0`; Azure
  groups absent (inherit `10.0`/`5.0`) — zero change to existing protection.

## Acceptance

- Independent review of this amendment in a separate session before
  implementation (repo workflow).
- Unit tests for inherit/override/unknown-group-refusal plus call-site wiring;
  80% coverage on new code; full suite, lint, type checks green.
- Staging re-validation of the shared-instance shape before production use.
