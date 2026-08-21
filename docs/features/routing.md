# Routing and Scheduling

## Status: Partially implemented

For each request: identify the model, find its configured candidates, remove disabled and cooldown backends when alternatives exist, estimate request cost, evaluate local credit safety reserve/capacity, score viable candidates, reserve before dispatch, forward, release reservation on completion, and return the response.

## Separate Quota from Credit

Quota represents rate or capacity constraints such as TPM/RPM. Credit represents a dollar or resource allowance. A backend can have high credit and exhausted quota, or available quota and insufficient safe credit. The router must consider both.

## Backend States

`ACTIVE` routes normally. `CONSERVATION` reduces traffic when projected cycle-end utilization is low or reserve pressure is rising. `PROTECTED` receives no intentional traffic. `QUOTA_COOLDOWN` and `ERROR_COOLDOWN` temporarily remove a backend after pressure or repeated transient errors. `DISABLED` is operator/configuration controlled. Protected emergency fallback is configurable.

## Credit and Cycle Policy

```text
spendable_credit = remaining_credit - safety_reserve
projected_unused_credit = remaining_credit - estimated_daily_burn * days_remaining
```

Prefer a usable backend that would otherwise waste more credit before its cycle ends, without crossing its reserve. Each backend has an independent cycle start day. Calculations must handle month lengths, February, leap years, month and year boundaries, and must represent the actual credit reset period rather than assuming invoice dates.

## Concurrency and Large Requests

Reserve a conservative estimated request cost before dispatch:

```text
available_credit = estimated_remaining_credit - reserved_inflight_cost - safety_reserve
```

Release the reservation and record local estimated usage after completion. Estimate large input and expected output cost before dispatch; if no backend can safely accept it, reject with `503` and `insufficient_credit_capacity` instead of risking exhaustion. These balances and costs are local estimates, not authoritative Azure balances.

## Scoring and Explainability

The initial explainable score may combine availability, quota health, credit health, cycle urgency, and error health. Every decision should expose model, selected backend, candidate states, scores, credit estimates, days remaining, and reason through structured debug data or authenticated status. Do not build an opaque machine-learning scheduler.

## Retry and Failover

Retry only transient `429`, `500`, `502`, `503`, and `504` failures by default. Allow one immediate backend failover by default, use bounded exponential backoff, honor `Retry-After` within a maximum delay, and never retry indefinitely. A 429 enters quota cooldown. No retry or failover occurs after streaming has meaningfully started.
