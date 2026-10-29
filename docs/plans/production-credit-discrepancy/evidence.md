# Production credit discrepancy evidence — October 29, 2026

## Evidence Log

| Item | Reference | Notes |
| --- | --- | --- |
| Live configuration | Azure control-plane readback and authenticated admin | Memory, one replica; revision suffix 0000004; static reconciliation, zero updated groups |
| Credit snapshot | Canonical admin credit group, approximately 12:12 UTC | fs-swarm allowance 210 USD, initial 83.621184 USD, remaining 11.7488519 USD, available 1.2488519 USD, no active reservations |
| Rejection | Retained sanitized logs, 11:41:31 UTC | gpt-6.1-sol estimate 1.59918 USD exceeds available 1.2488519 USD; fs-openclaw protected with zero allowance |
| Billing periods | Microsoft.Billing billingPeriods, API 2018-03-01-preview | Verified account-to-subscription mapping and current/prior periods below |
| Billing query | Azure Cost Management ActualCost / PreTaxCost | CAD; no continuation page; latest nonzero usage date October 26, with no October 29 cost rows |
| Local checks | Repository virtual environment | 52 existing credit/recovery tests passed; synthetic missing-usage and cached-input reproductions below |

## Verified billing-period dates

| Foundry account | Subscription display name | Current billing period, inclusive | Router cycle day |
| --- | --- | --- | --- |
| fs-swarm | Visual Studio Enterprise with MSDN | October 2–November 1, 2026 | 2, correct |
| fs-openclaw | Visual Studio Premium with MSDN | October 26–November 25, 2026 | 26, correct; allowance deliberately zero |
| af-opencode-agents | Visual Studio Professional Subscription | October 21–November 20, 2026 | Not a backend in this production router |
| alfer-mkokmbre-eastus2 | Visual Studio Professional Subscription | October 21–November 20, 2026 | Not a backend in this production router |

The Pay-As-You-Go subscription contained no Cognitive Services accounts in discovery. Prior records also start on days 2, 26 and 21 respectively. The initial hypothesis that fs-swarm should reset on October 26 was disproved by Azure's billing-period records; do not change its cycle day on that basis. The operator's approximately $12 Foundry estimate covers October 26–29, a shorter interval than fs-swarm's October 2 billing cycle.

## Why production rejects requests

The effective safety reserve is max(10 USD, 5% × 210 USD) = 10.50 USD. Available credit is remaining minus reserve minus inflight: 11.7488519 − 10.50 ≈ 1.2488519 USD. Recent gpt-6.1-sol admission estimates of 1.59918 USD and gpt-6-astra estimates of 1.63144 USD exceed that capacity. The rejection is consistent with the local ledger and reserve policy. Backend health was ACTIVE; no active reservations were holding up capacity. The tiny residual inflight value, approximately 2.7e-15 USD, is floating-point residue and does not explain the rejection.

The supplied request ID was absent from the retained application-log query. Recent requests establish the same failure mechanism, but are not represented as that exact request.

## Confirmed accounting and comparison discrepancies

1. **Starting estimate:** The October 14 subset promotion seeded fs-swarm with 83.621184 USD from its drained prior ledger, retaining allowance 210 USD/day 2. This historical local seed already represents 126.378816 USD less than allowance; it is not a fresh provider balance. See the [promotion packet](../opencode-gemini-streaming/production-packet.md). Static reconciliation currently reports success with zero updated groups and does not fetch Azure costs.
2. **Ledger/metric gap:** Snapshot debit since the loaded seed is 71.8723321 USD. Request-cost counters sum to 57.4305121 USD (astra 47.999020; luna 0.8608381; sol 8.570654), leaving 14.4418200 USD unexplained by those counters. Comparisons were sequential, not an atomic multi-endpoint snapshot. Production traffic was quiet in the queried recent interval. A known mechanism reproduces this gap, but historical attribution of every dollar is unverified.
3. **Confirmed observability defect:** Azure stream cleanup passes `charged_cost_usd=None` when terminal usage is absent. The credit store charges the full reservation, while metrics receives `estimated_cost_usd=None` and adds no cost. A local synthetic stream with a 4 USD reservation and no terminal usage debited 4 USD, recorded 0 USD cost, and left zero reservations. Reservation expiry also has no corresponding request-cost observation. Thus a cost dashboard can underreport actual ledger deductions. Conservative settlement itself follows the existing credit-integrity contract.
4. **Cached-token overestimate:** PricingConfig has only ordinary input/output token prices for Azure text. `estimate_response_usage_cost` ignores `input_tokens_details.cached_tokens`; streaming uses that same calculation. A local synthetic response with one million input tokens, all cached, at 2 USD/M input was charged 2 USD. Cache discounts cannot be represented. The proportion of the live gap caused by cache pricing remains unverified; no provider responses were captured and no inference was sent.
5. **Currency and freshness:** The successful resource-level cost query returned 129.042759285861 CAD for October 2–29, including only 0.179365116132 CAD on October 26 and no October 29 rows. This is returned reported cost, not a complete current balance or USD amount. No FX conversion was performed. FoundryModelEstimatedCost returned only astra and luna series in the bounded October 26–29 query, with no sol series and unit Unspecified; it does not independently establish the operator's complete $12 figure. Token metrics show substantial activity on October 29, so billing completeness cannot be assumed.

## Recommended remediation — Planned

- Reconcile a conservative current fs-swarm estimate using the verified October 2 cycle, correct currency conversion, complete resource scope and delayed/unreported usage. Do not reset to 210 USD or switch its day to 26 merely to restore admission.
- Add canonical ledger-debit telemetry distinguishing usage-priced, full-estimate and expiry/recovery charges, emitted from confirmed settlement. Ensure request-cost diagnostics explain the full charge when usage is unavailable without creating duplicate financial debits.
- Add independently reviewed, model/provider-specific cached-input pricing and validation, retaining full-price admission until cache hits are known. Confirm configured ordinary prices against the exact Azure deployment and pricing tier.
- Validate the existing opt-in Azure billing reconciliation adapter against these real subscriptions and CAD conversion before enabling it. Its downward-only ceilings do not replenish an already underestimated local balance; recovery of that balance needs an explicit reconciled seed/handoff.

No runtime code, secrets, deployment settings, ingress, allowances, reserves or production revisions were changed. Raw diagnostic captures and synthetic scripts remain local under /private/tmp; credentials were not printed or recorded.
