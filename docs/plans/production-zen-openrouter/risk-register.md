# Enablement risks

Mitigations below are planning requirements; they are not claims of deployed
controls. Execution evidence is required to close each risk.

| ID | Risk | Impact | Required mitigation | Status |
| --- | --- | --- | --- | --- |
| R1 | New pools replace or mix with Azure pools/aliases | Existing routing or pricing changes | Baseline-plus-delta validation; one exact backend per new pool, no new aliases; production adds Zen only | Open execution gate |
| R2 | Paid model assumed to exclude training/retention exposure | Unacceptable data use | Exact model allowlist plus current account/provider policy verification; no free or unacceptable data-use offers | Open execution gate |
| R3 | Prices, fees or token categories differ from assumptions | Underestimated debit or test spend | Recheck dated sources/units/charge policy, retain estimate labels, validate USD 0.01 six-case allowance; synthetic prices excluded | Open execution gate |
| R4 | Secret leakage or staging auth overwrites production auth | Credential exposure or client outage | Separate vault bundles; preserve production auth; no raw config/secret/version mappings in tracked evidence | Open execution gate |
| R5 | OpenRouter stream fails after public HTTP 200 | Partial output or missing terminal usage; HTTP-only monitoring misses it | Hold OpenRouter out of production; staging nonstream only; future enforced pre-admission control or reviewed streaming proof | Production exposure removed from scope |
| R6 | Restart/rollback restores spent credit or overlaps writers | Duplicate admission budget across all accounts | Stop admissions, drain, fresh conservative pinned seeds on every restart; no automatic rollback or stale revision reactivation | Open execution gate |
| R7 | Entire staging secret bundle promoted to production | Wrong Azure topology, auth or balance inputs | Same image and reviewed provider delta; environment-specific immutable bindings and current seeds | Open execution gate |
| R8 | Retained versions are not actually pinned/loaded | Mixed config or rollback silently uses newest secrets | Verify all changed references, loading behavior and saved deployment procedure; root is versionless except optional initial-credit pin | Open execution gate |
| R9 | Same paid account fully funded in two memory ledgers | Double-counted credit and spend | Shared-account ownership map, disjoint staging allocation, coordinated other writers and test-debit adjustment | Open execution gate |
| R10 | Separate model pools treated as separate credit/failure domains | OpenRouter balance counted twice; outage correlation missed | Canonical group per billed account, shared OpenRouter group where appropriate; group-level totals, independent quota mapping | Open execution gate |
| R11 | Unbounded or replayed validation | Additional paid traffic and ambiguous evidence | Six exact slots, durable reserve-before-egress, timeout/byte/token assumptions and estimated allowance, halt on any failure, no extra probes | Open execution gate |
| R12 | Untested image or deployment drift | Config accepted by different runtime; unrelated regression | Tested immutable digest and release diff; preserve current features, ingress and settings; amendment if template changes needed | Open execution gate |
| R13 | Staging/production unavailable or cannot be drained/observed | Unsafe handoff or unattributable settlement | Verify actual environments and operator procedure; stop if quiescence, account evidence or bounded validation cannot be proved | Open execution gate |
| R14 | Direct-probe success treated as router proof | Wrong root cause or premature streaming enablement | Keep evidence scopes separate; causal explanation remains unproven; no router rerun under old identities | Open execution gate |

## Decisions

- Reviewer recommendation incorporated: Zen-first production; OpenRouter staging
  nonstreaming only. A client-only restriction is insufficient for production.
- Keep `gpt-5.4-mini-zen` and `gpt-4o-mini-or`; use version-explicit
  `claude-haiku-4.5-or` for the staged Anthropic pool.
- Retain listed prices provisionally with dated provenance and recheck gates;
  they are local accounting estimates.
- Operator scope acceptance, maintenance window, quiescence method, actual
  immutable-secret deployment mechanism and named approvers remain pending.
- The reviewer accepts the [scoped public/admin acceptance amendment](amendment-black-box-acceptance.md)
  at plan level. Independent provider/billing equivalence is not claimed.
  All harness findings, including SV-1 reconciliation, SV-6 scope binding and
  SV-8 dispatch accounting, are independently closed in
  [82c7d09](review-staging-harness-9a763c7.md#follow-up-review-of-82c7d09).
  Untagged historical records and unsupported upstream flags are refused.
  Operator execution and production approvals remain separate.

## Staging evidence review update (2026-10-12)

The [review of be1f2c0](review-staging-evidence-be1f2c0.md) accepts the four
scoped staging case records. R11 is evidenced for those consumed slots; the
production slots and their approval gates remain open. R8/R12 remain open under
SE-2 (immutable release and secret-binding evidence), and SE-1 requires review of
the executed infrastructure scope, shared managed environment and reserve-policy
applicability. Case success does not close these operational risks.

R6/R9 require fresh production seeds for all accounts and a disjoint allocation
or controlled handoff from staging. Production reserve headroom must be checked;
staging's lower global reserve must not silently alter existing account policy.

The [release-packet follow-up](review-staging-evidence-be1f2c0.md#follow-up-supplied-release-packet-2026-10-12)
completes the SE-1 code review but leaves operational proof open. SE-2 remains
partial despite the candidate digest: immutable deployed bindings are not proved.
SE-3 rejects the proposed Zen-only seeds/global reserve reduction for the existing
app. The target remains the preserved Azure baseline plus Zen; all retained
accounts participate in a memory restart. Named human owners remain required.

The [group reserve design review](review-group-reserves-df5396c.md) approves
local implementation of canonical group overrides with unchanged inherited Azure
settings. This addresses SE-3's policy concern at design level only; all-account
seeds, shared-account allocation, implementation verification and operational
approvals remain open. Mixed-policy admin/metrics and fresh release-bound staging
evidence are explicit gates; the old four passes cannot qualify the new image.

The [f891d06 implementation review](review-group-reserves-f891d06.md) verifies
the exercised reserve values and mixed-policy diagnostics but leaves GI-1 open:
inherited policy resolution causes repeated full backend scans per candidate.
GI-2 recommends read-only validated maps. These are local implementation issues;
no live requests are needed to fix or verify them. Implementation clearance and
new-release staging/production gates remain open.

The [48012df follow-up](review-group-reserves-f891d06.md#follow-up-review-of-48012df)
closes GI-1/GI-2 and clears local implementation review. Validated steady-state
resolution performs no backend scans and parsed maps reject content mutation.
Fixture cache-miss fallback is not a supported hot-reload mechanism. Release,
shared-account/fresh-seed and new staging/production execution gates remain open.

The [57bee77 roster review](review-openrouter-roster-57bee77.md) leaves three
Major planning gates open: non-streaming production enforcement (OR-1), usable
shared-account reserve/allocation (OR-2), and bounded new-release validation with
correct promotion evidence (OR-3). R5 is removed from exposure only while the
existing exclusion of OpenRouter production is retained. Catalog membership,
prices, performance claims and account data policy need distinct evidence;
no new roster configuration or spending is approved.

The [efd13ab catalog evidence follow-up](review-openrouter-roster-57bee77.md#evidence-follow-up-efd13ab)
checks the retained five-entry artifact and price-unit arithmetic, and records
source locations and the operator's funding-fee clarification. This closes the
missing-artifact/source-location portion of OR-4, not the three Major roster
gates or current provider/account policy and billing limitations.

The [3bd4010 staging execution review](review-roster-execution-3bd4010.md) clears
local harness implementation of the revised five-case staging contract. It binds
a distinct inherited/overridden policy contrast and requires retained release/
policy evidence; actual harness/configuration/approval gates remain open. OR-1
remains a production blocker, not a requirement to enable streaming before an
operator-only non-streaming staging run. Production policy/allocation and the
production execution amendment remain separate from this staging plan.
