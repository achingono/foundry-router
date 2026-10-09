# Redacted Azure cost schema diagnosis

**Implemented** locally and the single diagnosis completed, 2026-10-08. The first group
returned non-USD currency; strict USD-only billing acceptance remains unverified.
The immutable prior diagnostic reached provider response validation
and reported only `schema`. The accepted billing contract remains USD-only ActualCost,
exact resource membership and complete nonempty rows; no balances or permissions change.

After independent review, implement a read-only observer around the existing provider's
bounded HTTP transport. Use the same two operator-mapped groups, Azure CLI identity,
30-second refresh deadline, 1 MiB pages, ten pages and 10,000 rows per group. Exactly one
invocation, no retries. Reuse existing two bounded metadata discoveries. Preserve both prior
results and their started markers; use a new atomic started/result pair and whole-invocation
OS lock. Refuse replay even after interruption. Stop at the provider's first validation failure;
do not send a separate raw billing probe or fetch extra pages/groups to diagnose it.

The observer may inspect the bounded response already received by the provider and emit only
fixed booleans/enums/counts: HTTP status category (success/auth/other), valid JSON flag,
properties/columns/rows list flags, column count capped at 32, row count capped at 10,001,
presence/type validity of `PreTaxCost`, `Currency`, `ResourceId`, unknown-column count capped
at 32, any missing/nonfinite/negative amount flags, currency classification `USD`/`non_USD`/
`missing_or_invalid`, all-resource-membership flag and consistent row-width flag. Unknown
column names, IDs, amounts, error bodies, tokens and exception text never enter evidence.
No arbitrary strings/keys/lengths from provider objects. Oversized/deep/malformed bodies produce
fixed rejected flags. Decode only within existing bounds and avoid reading a response twice;
preserve the provider's unchanged parsing/validation and cleanup behavior.

Use a small transport wrapper or explicit observer injection at the owning verifier boundary;
do not loosen runtime billing logic or add general production diagnostics. Require exact safe
schema validation before persisting/displaying observer results. Bind safe observations to
group labels and pagination indices; observations cannot establish accepted billing ceilings.
Typed provider failures are mapped through a fixed validation-code allowlist (no raw strings).
Preserve response data only in memory for the normal provider parser; do not retain raw bodies.

Test malicious unknown names/values, wrong currency, absent/duplicate/wrong-type columns,
invalid rows/amounts/resource membership, oversize/deep responses, observation bounds,
unchanged provider acceptance/rejection, cleanup and consumed-start replay suppression.
Run required focused/full quality and independent contextual review before the one invocation.
No Docker rebuild for verifier-only code. Record exact cause category if proven; non-USD data
must remain rejected until a separately reviewed currency/budget policy exists. Do not infer
promotional balance or reported cost from a clamped ceiling. Production remains memory/one.

- [Inputs](inputs.md)
- [Activities](activities.md)
- [Outputs](outputs.md)
- [Exit criteria](exit-criteria.md)
- [Risks](risk-register.md)
- [Evidence](evidence.md)
