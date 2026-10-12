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
  SV-1 reconciliation is independently closed. SV-6 evidence-scope binding
  remains open; untagged historical records and unsupported upstream flags must
  not be accepted as the revised contract.
  Operator execution and production approvals remain separate.
