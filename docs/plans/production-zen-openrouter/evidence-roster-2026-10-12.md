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
| `roster-deepseek-nonstream` | **failed**, HTTP 502 in 0.73s, `acceptance_mismatch`, dispatched | Unmeasured |
| `roster-mimo-nonstream` | not attempted (halted ledger) | — |
| `roster-spark-nonstream` | not attempted (halted ledger) | — |

The local estimated debit subtotal for the two passing cases is USD 0.0000079;
this is not a provider billing total. The failed case returns before closing
admin observation, so its persisted zero debit is an initialization default
and its debit and cleanup are unverified by the case record. The HTTP 502 and
0.73-second duration do not establish whether the cause was provider rejection,
transport, router preparation or protocol validation. Diagnosis remains open.
The halted ledger refuses resume; any rerun needs a new reviewed identity and
bounded execution amendment. No direct probes were sent; no credentials,
prompts, or outputs are recorded here.

## Completion verification follow-up

The harness implementation and review fixes are committed as `e34b506`,
`2e18d6f` and `d5d808a`. On October 12, a fresh read-only Azure control-plane
check reported provisioning `Succeeded`, ready revision
`foundry-router-staging--0000002`, the recorded `grimsugar` image tag, and
`maxReplicas: 1`. A tag readback does not independently attest the running digest.
Historical digest, seeds, grant removal and owner/quiescence details above are
retained execution observations; this follow-up does not re-attest them.

Fresh local checks passed: 69 harness tests with 81.01% harness coverage,
repository Ruff lint and format (919 files), Mypy (72 source files), a local
Docker build, and 15 Azurite integration tests. The SonarQube script is absent,
so that conditional check is not applicable. Independent contextual review
found no new blocking implementation finding and required the financial/cause
correction above. The [completion report](completion-2026-10-12.md) records
2,505 full-suite passes and 89.47% runtime coverage, plus successful health/admin
readback with zero active/inflight reservations on both groups. Current quietness
does not establish the failed case's historical debit or cause.
