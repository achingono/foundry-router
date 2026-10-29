# Independent pricing/configuration amendment review — October 29, 2026

**Current verdict: Approved for preparation of the exact production packet.** The revised table resolves Major P1. This is monetary/configuration scope approval, not approval of an unprovided deployment packet or live acceptance.

## Re-review of revised amendment

Reviewed revised [pricing amendment](pricing-amendment.md), SHA-256 `15f6942f80a372a86dc445271e23ffda84625c1dbba55a2f3de4b7d6ba5a4dd2`. Independently recomputed maxima across all matching USD/1M/eastus Standard Global and Priority Processing Global rows in the complete 168-row catalog capture. The revised input/cached/output triples match exactly:

| Pool | Input | Cached input | Output |
| --- | ---: | ---: | ---: |
| gpt-5.6-luna | 1.00 | 0.08 | 3.60 |
| gpt-5.6-terra | 10.00 | 0.80 | 36.00 |
| gpt-5.6-sol | 20.00 | 1.60 | 60.00 |
| gpt-6-luna | 0.25 | 0.02 | 0.75 |
| gpt-6-astra | 25.00 | 2.00 | 75.00 |
| gpt-6.1-sol | 5.00 | 0.20 | 15.00 |

All values are USD/M tokens and remain conservative local estimates over the verified catalog scope. The revised document explicitly accounts for forwarded service tier and does not invent absent GPT6 priority rates. No source/API policy change is needed for this correction.

The independently checked USD142.49 allowance/USD128.24 starting estimate, verified day26 cycle and at-most-USD0.00512 local estimate for the bounded gpt-6.1-sol pair remain unchanged. **P1 is resolved; no remaining Critical/Major monetary-amendment finding.** The initial verdict and reasoning below are retained as review history.

Before actual inference, the separate packet must bind exact literal requests, price/config pins, current deployment identity/SKU/version evidence, unique nonreplayed slots and the acceptance budget. If the tiny pair reports zero cached tokens, it validates ordinary settlement and stream transport but must not be represented as observed nonzero cached-token discount acceptance. Production handoff, all-account seed conservation and post-deployment readback remain required.

## Initial review — superseded by the re-review above

Initial verdict: Changes required before using the initial pricing table in a live packet. The allowance conversion and bounded gpt-6.1-sol pair were acceptable; one Major service-tier coverage issue remained in the six-pool pricing ceiling.

Reviewer: independent `credit_plan_review` / `gpt-6-astra` session; no source or amendment edits. Reviewed [pricing amendment](pricing-amendment.md), SHA-256 `78d2cc8bb9f4259fbb507e17b784fc6290f1253dc9e245df522bfb72995dddb0`, alongside the approved implementation and Azure pass-through boundary.

## Major P1 — Standard-only prices do not cover the admitted service-tier surface

- **File/Module:** [pricing amendment](pricing-amendment.md), pricing policy/table; `src/foundry_router/api/adapters/azure.py`, request checking and body construction.
- **The Issue:** The amendment takes maxima only from `Std Gl` rows. The Azure adapter accepts and forwards request fields, including `service_tier`, without enforcing a Standard-only policy. The same matched catalog contains higher `PP Gl` prices for all three gpt-5.6 pools. A `GlobalStandard` deployment SKU by itself is not evidence that priority-processing requests cannot apply.
- **Why Static Analysis Missed It:** The flaw depends on matching live price dimensions with externally selectable provider behavior; each configuration value is individually valid.
- **Impact:** If priority processing is admitted, the purported conservative ceilings can underprice that traffic. In the supplied complete catalog, the maximum Global priority input/cache/output triples are 1.00/0.08/3.60 for gpt-5.6-luna, 10.00/0.80/36.00 for gpt-5.6-terra and 20.00/1.60/60.00 for gpt-5.6-sol, twice the proposed values.
- **Recommended Fix:** Supply verified evidence that priority processing is unavailable/disabled for these exact deployments, or amend the no-source-change configuration ceilings to cover the observed applicable priority rates as well. Alternatively, an explicit Standard-only request policy is a source/API amendment requiring separate review and verification. Do not invent doubled prices for GPT6: the reviewed catalog contains no GPT6 `PP Gl` rows. The gpt-6.1-sol acceptance budget is unaffected if its 5.00/0.20/15.00 triple remains.

## Independently checked facts

- Read `/private/tmp/router-retail-all-six.json`: 168 rows, no continuation page, SHA-256 `e33090ccefa2026fe8301c44984502193b1d484b2ca1ca113367b385d2052c5b`. All six proposed triples correctly equal the maxima of their USD/1M/eastus `Std Gl` ordinary-input/cache-write, cached-read and output rows. All observed effective start dates precede this review. The issue is service-tier scope, not arithmetic on Standard rows.
- Decimal cents-floor calculations: CAD200 / 1.4036 = USD142.49; CAD180 / 1.4036 = USD128.24. These agree with the amendment. The reported October 28 Bank of Canada rate and user-supplied CAD amounts are coordinator evidence; the review does not infer a provider balance from incomplete usage rows.
- At 5 USD/M input and 15 USD/M output, two 128-input/128-output calls have a local ceiling of USD0.00512, within USD0.01. The exact packet must bind the literal tiny synthetic bodies and validate this estimate before dispatch; token estimates are not a provider-billed-token guarantee. No retries/replays and abort-on-ambiguity remain required.
- Allowance/cycle handling and preservation of other account seeds remain consistent with the approved drained memory/one handoff. No historical refund, billing-provider activation or source change is introduced by the monetary amendment.

At the initial review, no live mutation or inference was approved and P1 required amendment/re-review. The completed re-review above resolves that finding; exact image/configuration pins, live allowance/pricing readback and handoff/acceptance remain a subsequent packet gate.
