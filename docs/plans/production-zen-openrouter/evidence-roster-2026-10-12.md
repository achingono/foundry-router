# Roster staging execution evidence

Date: 2026-10-12. Run: `staging-or-roster-2026-10-12`.
Status: **Halted on case 3 of 5 by design; no replay, no successor dispatch.**

## Deployment (pre-dispatch, verified)

- App `foundry-router-staging` in `rg-foundry-router-staging-eastus`, attached to
  production environment `foundry-router-env-production`.
- Image `grimsugar.azurecr.io/foundry-router:zen-openrouter-roster-efd13ab`
  @ `sha256:71addc1701611f4c6210df28007b3f03d57eb05b9ccd3fe9eed4e6a13e4165ff`
  (byte-identical re-push of the reviewed build; the `chingono` registry
  subscription began refusing writes and then reads mid-operation, and the
  prior revision was failing image pull).
- Global reserves 10.0/5.0; `or-shared` override 0.05/5.0 (`override`);
  `zen-staging` inherited 10.0/5.0; zero inflight/active on all groups;
  headroom contrast provable (4.5785 under override, negative under the
  USD 10 floor). Eight pools served, including the five roster pools.
- Fresh conservative seeds: `or-shared` 4.82, `zen-staging` 9.99
  (floored below confirmed actuals 4.83/10 after prior-run spend).
  Temporary provisioning grant removed. Owners: execution/monitoring Alfero;
  quiescence confirmed; catalog excerpt accepted as current.

## Results (ledger/results in stage dir, git-ignored)

| Case | Result | Debit |
|---|---|---|
| `roster-luna-nonstream` | passed, HTTP 200, policy (0.05, 5.0, override), settled, cleared | $0.0000037 |
| `roster-haiku-nonstream` | passed, HTTP 200, policy (0.05, 5.0, override), settled, cleared | $0.0000042 |
| `roster-deepseek-nonstream` | **failed**, HTTP 502 in 0.73s, `acceptance_mismatch`, dispatched | $0 |
| `roster-mimo-nonstream` | not attempted (halted ledger) | — |
| `roster-spark-nonstream` | not attempted (halted ledger) | — |

Total spend $0.0000079. The halted ledger refuses resume; any rerun needs a
new reviewed identity. The 502 arrived in 0.73s (provider-side rejection
propagated, not a timeout); diagnosis of the DeepSeek path and the rerun
scope are open review items. No direct probes were sent; no credentials,
prompts, or outputs are recorded here.
