# Inputs

## Required Inputs

| Input | Source | Owner |
|---|---|---|
| Production app reference (FQDN/resource group/app name, operator-supplied at runtime; never committed) | Operator session | Operator |
| Production client/admin keys via captured token-authenticated vault reads; temporary Secrets User grant removed in `finally` if needed | Production vault, same procedure as `production-inference/activities.md` | Operator |
| Verified production configuration scope (two resources, six pools, 12 backends, two credit groups, memory/one) | `../production-foundry/evidence.md` | Operations |
| Prior `fs-swarm` inference scope and routing-coverage limits | `../production-inference/evidence.md` | Operations |
| Admission/failure contract (auth, 404/4xx/422/503 `insufficient_credit_capacity`, 429/5xx cooldown + single failover, no retry after streaming starts, `Retry-After`/`Cache-Control` propagation only) | `../../api/index.md`, `../../features/routing.md`, `../../operations/index.md` | Engineering |
| Local admission/failover regression coverage | `tests/unit/test_main.py` (admission, cooldown, single-failover, SSE-error-without-failover cases) | Engineering |
| Live-traffic authorization for this bounded scope | Current user request | Operator |

## Optional Inputs

- Operator-confirmed lowest-cost `fs-swarm` pool for the two inference probes (default: cheapest configured pool at runtime prices; no new pricing committed).
- Existing production diagnostics snapshot for before/after comparison.

## Input Validation Checklist

- [ ] All required inputs are current (not from a superseded version)
- [ ] No required input is missing or in draft state
- [ ] Production app reference and keys exist only in memory or owner-only gitignored payloads; no credential, subscription-ID, endpoint, or deployment-ID literals in docs
- [ ] Independent plan review approval recorded before live traffic
