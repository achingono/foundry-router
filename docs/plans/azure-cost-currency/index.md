# Subscription billing currency and daily CAD conversion

**Planned**, 2026-10-08. Operator confirmed all current subscriptions bill in CAD and
requested publicly available daily average conversion, with currency configurable per
subscription. Prior [schema diagnosis](../azure-cost-schema-diagnosis/evidence.md) observed
non-USD billing for fs-openclaw; this is the concrete requirement for extending USD-only cost
acceptance. Production remains memory/one; implementation grants no deployment permission.

## Configuration and accounting contract

Add `FOUNDRY_COST_MANAGEMENT_SUBSCRIPTION_CURRENCIES_JSON`, an optional exact mapping from
subscription UUID to billing currency `USD` or `CAD`. Normalize UUID case, reject duplicate
normalized keys/unsupported currencies/non-string values and unused mappings; retain USD
as the compatibility default for unmapped subscriptions. Resolve each configured cost group's
subscription from its validated billing scope. Different groups of one subscription use one
currency; do not configure currency per backend or infer it from an endpoint. For the current
operator acceptance mapping explicitly configure CAD for every discovered subscription.
Private real subscription IDs remain gitignored; examples use synthetic placeholders.

Local cycle allowances, reservations, prices and estimates stay in USD. Require every returned
cost row/page/group to use the exact resolved billing currency; reject mixed or unexpected
currencies. USD cost remains unchanged. Sum validated CAD cost for each group, then divide by
one validated CAD-per-USD daily average rate for the entire refresh. Compute USD ceilings with
high-precision decimal arithmetic, rounding converted costs upward and remaining ceilings
downward; preserve existing atomic downward-only application and inflight reservations.
Bind resolved billing currency into the cost-policy fingerprint so a configuration change
invalidates a fetched ceiling. Rate changes never replenish local debits.

## Public rate source and freshness

Use only Bank of Canada [Valet FXUSDCAD](https://www.bankofcanada.ca/valet/observations/FXUSDCAD/json?recent=10).
Its [published methodology](https://www.bankofcanada.ca/rates/exchange/daily-exchange-rates/)
defines an indicative daily average, CAD per one USD, normally published business days by
16:30 ET. A read-only source check on 2026-10-08 returned dated observations and rate 1.4240
for that day; this is evidence of source shape, not a hard-coded runtime rate.

Fetch one public rate snapshot per complete refresh only when CAD groups exist, inside the
existing 30-second total deadline including token/billing work. Use fixed HTTPS origin/path/
query, no auth/ambient proxy/redirect/retry, 5-second subdeadline, 64 KiB body cap, bounded JSON
depth and at most ten observations. Require exact series metadata identifying FXUSDCAD,
unique ISO dates and finite positive decimal-string rates bounded to [0.1,10] with at most
12 fractional digits. Reject malformed/missing/nonfinite/duplicate entries. Select latest
published observation whose date is not in the future in America/Toronto; reject any future
date rather than silently ignoring tampered records. Accept latest observation age at most
four calendar days to cover ordinary weekends/holidays; later publication delays fail closed.
No inferred holiday values, interpolation, zero/default rate or stale-rate fallback.

This applies the latest daily average to cycle-to-date CAD aggregate as an operational USD
estimate; it does not reconstruct transaction-day conversion or Azure's own billed FX. Retain
source/date/rate and conversion method in typed fetched evidence and safe acceptance output.
USD-only refreshes perform no public rate fetch. Currency/rate failure rejects the whole fetch
before balance application; reservation reaper and existing local estimates remain independent.
Own/close rate transport with the existing provider lifetime, including cancellation and startup
failure. No independently detached refresh task or mutable global rate cache.

## Verification and bounded acceptance

Obtain independent plan review before code. Test per-subscription currency resolution and
fingerprint changes, mixed currency rejection, rate direction/rounding, USD no-extra-egress,
fresh/weekend/stale/future/duplicate/malformed rate cases, body/depth/time/transport cancellation,
provider lifetime and unchanged downward-only memory/Table application. Run focused/full quality,
Docker and contextual review for runtime changes; document config/operations/traceability.

After local review, one immutable read-only acceptance invocation, two bounded account metadata
discoveries and one complete refresh with one rate fetch and at most two group queries under
the existing pagination/deadline bounds. Configure current subscription currencies CAD from
operator input; retain prior failed results and markers. New OS lock/started/result pair refuses
repeat or interrupted replay. Output safe group labels, rate source/date/CAD-per-USD, USD ceiling
estimates and fixed failure categories only; never raw costs/resource IDs/keys/errors. No applied
balances, grants, deployment or production change. Empty/partial/wrong-currency responses remain
unverified. Successful acceptance clears only the recorded currency/query scope.

- [Inputs](inputs.md)
- [Activities](activities.md)
- [Outputs](outputs.md)
- [Exit criteria](exit-criteria.md)
- [Risks](risk-register.md)
- [Evidence](evidence.md)
