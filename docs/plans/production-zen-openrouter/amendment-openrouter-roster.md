# OpenRouter production roster amendment — changes required

Date: 2026-10-12. Status: **Proposed; independent review not cleared.**
See [review of 57bee77](review-openrouter-roster-57bee77.md). No code or
configuration is changed by this amendment. It proposes five paid OpenRouter
pools but does not supersede the approved Zen-first production scope. No staging
vault write, rollout or live dispatch is cleared by this record.

## Candidate roster

The operator supplied a [committed catalog excerpt](catalog-openrouter-excerpt-2026-10-12.json)
captured at `2026-10-12T13:48:27Z` from `GET /api/v1/models`. The
[evidence follow-up](review-openrouter-roster-57bee77.md#evidence-follow-up-efd13ab)
checks all five IDs and per-token conversions against this roster. These remain
provisional catalog inputs, not independently tested router capability or billing
evidence; recheck IDs, units and applicable charge categories day-of.

| Pool | Proposed deployment | Proposed USD/M input / output |
| --- | --- | --- |
| `gpt-6-luna-or` | `openai/gpt-6-luna` | 0.10 / 0.50 |
| `claude-haiku-5.5-or` | `anthropic/claude-haiku-5.5` | 0.10 / 0.50 |
| `deepseek-v4.1-flash-or` | `deepseek/deepseek-v4.1-flash` | 0.15 / 0.60 |
| `mimo-v2.6-flash-or` | `xiaomi/mimo-v2.6-flash` | 0.14 / 0.28 |
| `muse-spark-1.3-contributor-or` | `meta/muse-spark-1.3-contributor` | 0.10 / 0.20 |

Flagships and all `:free` variants remain excluded from this proposal. The
original draft's volume/speed/benchmark source links are retained in the evidence
follow-up but their contents have not been independently verified. The operator
clarifies the reported 5.5% (USD 0.80 minimum) fee is for top-ups, not an inference
rate adjustment. Current applicable terms still need checking. Paid status alone
does not establish acceptable retention/training terms.

## Proposed configuration and unresolved boundaries

- One backend per exact deployment; one single-backend pool at weight 1.0 each.
  Keep distinct logical pools and no Azure fallback/new aliases. Define an exact
  baseline-plus-delta roster, including the disposition of the two existing
  staging OpenRouter pools, before preparing the execution manifest.
- All five share canonical `or-shared` only if backed by the same billed account.
  Quota ownership remains separate. Staging/production ledgers must not each
  receive the full shared balance; allocation or controlled handoff is required.
- **OR-1 open:** `responses` does not restrict stream mode. Production requires
  either a reviewed pre-admission enforcement feature with zero-dispatch negative
  tests, or separately qualified streaming and an explicitly revised policy.
  Until then, candidates may only be considered for operator-controlled staging.
- **OR-2 open:** “No reserve-map change” is not viable for the stated USD 4.83
  account under inherited USD 10 / 5% production settings. Propose an explicit
  `or-shared` group policy/current allocation or establish headroom under existing
  policy. Preserve Azure/Zen policy and fresh seeds for all retained accounts.
- **OR-3 open:** A new identity must be backed by a reviewed execution amendment
  and harness changes. Current immutable manifests/specs do not contain this
  roster. Define exact calls, prices, limits, allowance, durable files and
  promotion checks bound to the new image/configuration and new staging evidence.
  This must also account for the outstanding group-reserve shared-instance check.

The [staging-only execution amendment](amendment-roster-execution.md) specifies
a concrete OR-2 staging policy and OR-3 five-case design, reviewed for local
harness implementation. This does not clear deployment/live gates or OR-1
production enforcement. Staging can proceed after its own implementation/input/
operator gates without first enabling OpenRouter production.

## Acceptance gates

- [ ] Resolve OR-1 production streaming policy/enforcement and review it.
- [ ] Resolve OR-2 shared-account reserve, fresh inputs and staging allocation.
- [x] Retain/review the supplied catalog excerpt, exact capture time, source links and per-token conversions.
- [ ] Recheck day-of catalog/charge applicability and account/provider data-use terms; catalog evidence is not live inference qualification.
- [ ] Resolve OR-3 with immutable manifests and independently reviewed harness;
      retain all historical ledgers closed and unchanged.
- [ ] Review concrete staging release/configuration/version/maintenance inputs
      before vault writes or rollout; obtain the existing operator approvals.
- [ ] Execute and independently accept only the newly authorized staging cases.
- [ ] Separately review production release/policy, all-account seeds, bounded
      production checks, monitoring/rollback ownership and operator approval.

The draft prices imply USD 0.00056832 for five hypothetical 512-input/128-output
checks; this is an illustrative input/output-only estimate, not an approved
allowance or verified provider charge. The prior USD 4.83 figure is not a fresh
balance confirmation, and the previous 5,000-request runway claim is withdrawn.
