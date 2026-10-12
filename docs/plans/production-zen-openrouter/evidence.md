# Enablement evidence

**Deployment planned; harness implemented locally.** No staging/production
writes or live inference were performed by the reviewer. Independent plan and
harness review are complete; environment preparation and execution approvals
remain pending.
The independent harness review gate is cleared for `82c7d09`: all seven Major
findings and SV-8 are closed under the narrowed public/admin acceptance contract.
Actual-environment, release, maintenance and operator execution gates remain open.

| Item | Reference | Notes |
| --- | --- | --- |
| Independent plan review (2026-10-11) | [Review](review.md) | Four Major planning findings and two Suggestions addressed in the revised contract; execution proof remains required |
| Streaming decision | [Index](index.md), R5/R14 in [risks](risk-register.md) | Zen-first production; OpenRouter absent from production; staging nonstream only; client guidance is not enforcement |
| Pool names / prices | [Configuration table](index.md#pools-prices-and-account-ownership) | Haiku version explicit; prior configured prices retained provisionally, current provenance/policy check pending |
| Review verification | Repository source and canonical docs | Checked backend capabilities, translated-stream failure behavior, credit ownership, memory handoff and template secret binding; no tests or live requests needed for this documentation review |
| Documentation checks | Revised plan | Relative links, whitespace and final diff checked |
| Release and execution prerequisites | [Exit criteria](exit-criteria.md) | Actual environment baseline, image, secret-selection mechanism, maintenance, manifests/harness and operator approvals pending |
| Staging harness | `scripts/quality/staging_validation.py`, `tests/unit/test_staging_validation.py` | 48 offline checks: immutable specs, combined allowance, single-backend/single-shot enforcement, bounded reads, strict SSE terminals, whole-prefix reconciliation with coherence revalidation, precision-derived settlement, inference-only entry accounting, evidence-scope binding, narrowed production gating, redaction |
| Staging deployment (2026-10-12) | `rg-foundry-router-staging-eastus`, image `zen-openrouter-staging-4224eaa` | New group holds vault `kv-fr-stg-002`, runtime identity, app; app attached to production environment `foundry-router-env-production`. Eight secrets populated before provisioning; temp Secrets Officer removed. Credit groups `zen-staging` (10.00/10.00) and shared `or-shared` (4.83/4.83) seeded at operator-confirmed actuals; staging reserves 0.05/5% via parameterized template. Prod group clean except self-deleting staging env. No credential values recorded |
| Staging validation run (2026-10-12) | Run `staging-zen-openrouter-2026-10-11`, ledger/results in stage dir (git-ignored) | 4/4 passed, all HTTP 200, usage coherent, terminated, settlement matched, reservations cleared. Debits: zen-nonstream 3.15e-05, zen-stream 3.15e-05, openai-nonstream 3.15e-06, haiku-nonstream 3.8e-05; total 0.00010415 USD under the 0.01 allowance. Quiescence confirmed by approver; no other traffic during run |
| Independent harness review (2026-10-11) | [Review of 9a763c7](review-staging-harness-9a763c7.md) | Initial review: seven Majors on state/promotion validation, immutable case/aggregate-budget binding, upstream attempt limits, response bounds, SSE framing, missing independent proof and settlement tolerance; follow-up below supersedes dispositions and corrects the Zen retry attribution. One dispatch-evidence Suggestion. 21 tests passed; independent fake-app reproductions confirmed gaps. No live requests or staging writes |
| Harness follow-up (2026-10-12) | [Review of febe207](review-staging-harness-9a763c7.md#follow-up-review-of-febe207) | SV-2/3/4/5/7 closed; SV-1 and SV-6 remain open; SV-8 partial. 57 focused tests passed, plus independent state, mutation, bounds, stream and debit checks. No live requests |
| Narrowing decision (2026-10-12) | [Scoped acceptance amendment](amendment-black-box-acceptance.md) | Reviewer accepts deployed public/admin acceptance without independent provider/billing claims; six-case budget and operator gates unchanged. Implementation/re-review pending; no execution clearance |
| Harness second follow-up (2026-10-12) | [Review of 08221ff](review-staging-harness-9a763c7.md#follow-up-review-of-08221ff) | SV-1 closed; SV-6 remains partial because scope is not bound and legacy/true-upstream-flag records are accepted. SV-8 remains partial; its claimed marker/harvesting fix is absent. 43 tests plus independent state, scope, replay and bounds checks. No live changes |
| Harness final follow-up (2026-10-12) | [Review of 82c7d09](review-staging-harness-9a763c7.md#follow-up-review-of-82c7d09) | SV-6/SV-8 closed; all prior findings remain closed. Independent harness review gate cleared for the six scoped cases. 48 tests plus independent scope/legacy/promotion/replay and entry-failure probes passed. No live requests or staging writes |
