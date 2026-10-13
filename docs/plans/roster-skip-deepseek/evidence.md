# Skip-DeepSeek staging evidence

Date: 2026-10-12. Status: **Harness implemented; existing staging deployment retained; remaining live acceptance blocked by intermittent health timeouts**.

## Scope and reviews

User authorized proceeding without DeepSeek and confirmed staging. DeepSeek was excluded from these validation requests; its existing staging configuration remains. No production change, vault write, rollout, restart, grant or new resource occurred. MiMo/Spark pools were already deployed on ready revision `foundry-router-staging--0000002`, with the recorded image tag and maxReplicas1. The fresh preflight returned ready,8pools,global reserves10/5,OR override0.05/5,Zen inherited10/5,and both groups quiet.

Independent [plan and implementation reviews](review.md) approved the initial two-case identity and the final timeout amendment. Old ledgers/results remain unchanged. The five-manifest configured-price estimate is USD0.00608256 within the existing USD0.01 allowance; abandoned allocations are not refunded. This is a local estimate,not provider billing.

## Verification

- 80 focused tests passed; harness coverage81.41%.
- Full suite2,516 passed,3 skipped,19 deselected; runtime coverage90.08%.
- Ruff lint/format923 files and Mypy72 source files passed.
- Sonar conditional script absent; no scan claimed. Docker omitted because application source/image unchanged.
- Initial final-identity offline test expectation was corrected: missing aggregate prerequisites precede slot reservation. Separate health failure test verifies reserved-slot resume refusal. Independent reviewer re-ran80 tests and cleared implementation.

## Execution observations

1. `staging-or-roster-remaining-2026-10-12`: harness five-second `/health/live` timed out before inference. MiMo slot remains reserved/unresolved; Spark unreserved. No inference POST sent. Ledger/identity preserved; no reset or resume.
2. Read-only health diagnosis subsequently returnedHTTP200 with direct and environment-configured routing, establishing intermittent reachability only.
3. `staging-or-roster-final-2026-10-12`: read-only15-second urllib health warmup timed out before calling the harness. No final ledger/identity/results were created,and no inference POST was sent. The amendment prohibits another attempt after this refusal; none performed.

## Outcome

DeepSeek was skipped. Existing staging configuration is deployed,but MiMo/Spark remain unverified. Historical Luna/Haiku passes remain separately scoped; no four-model or five-model pass is claimed. Health/admission reachability investigation and a reviewed next execution scope are required before further live checks. No production qualification follows.
