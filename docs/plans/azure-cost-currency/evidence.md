# Currency Evidence

Operator requests all-current-subscription CAD, publicly available daily average and
subscription-specific configurable currency. Public Bank of Canada FXUSDCAD source read
returned daily average CAD-per-USD metadata and 2026-10-08 rate1.4240. No conversion/runtime
change existed at source discovery; no new billing invocation had been dispatched.

Local implementation now validates per-subscription USD/CAD mappings, binds currency into
the pre-await policy snapshot and uses one dated unauthenticated public rate per CAD refresh.
USD-only refreshes perform no FX egress. Conversion rounds cost upward and USD ceilings
downward. Rate acquisition occurs after provider ownership so setup failures remain cleanable.

Verification: 28 currency tests pass, including currency changes during public-rate I/O and
Table CAS retry, multiple CAD groups/one rate, repeating-decimal rounding, stale/future/
duplicate/invalid/bounded rate evidence and startup cleanup. Full suite: 1,919 passed,
3 skipped, 18 Docker/Azurite tests deselected, 89.74% coverage. Real Azurite cost-ceiling
concurrency/restart test passed separately. Ruff lint/format and mypy (70 source files)
pass. Linux/amd64 Docker build and runtime currency imports/Toronto timezone smoke pass.
Updated document links and diff whitespace pass. Sonar scanner script is absent.

Independent contextual review found a partial-acquisition lifecycle issue, fixed by lazy
owned rate acquisition and failure-injection verification. Final review reports no Critical
or Major findings; single immutable CAD acceptance entrypoint also cleared. Canonical
configuration, operations, security, traceability and routing roadmap are updated.
The single immutable read-only CAD acceptance invocation completed in 6.129 seconds with
`status: unverified`, provider-boundary `http_rejection`, no accepted groups and
`balance_applied: false`. See [result](diagnostic-results.json) and
[consumed invocation marker](diagnostic-started.json). Public-rate validation preceded
billing requests, but no complete batch/rate metadata was returned, so no numerical live
conversion claim is made. Billing rejection does not establish authorization, data
completeness or either group's accepted ceiling. No raw HTTP error was retained; do not
infer its status or cause. No automatic retries or replay; prior failures remain unchanged.
Live two-group CAD acceptance remains unverified; production has not changed.
