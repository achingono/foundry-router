# Table production and autoscaling Evidence

## Status: Partially implemented (preflight verification); production migration Planned

Plan authored 2026-10-30. No implementation, Azure calls, deployment, paid dispatch, restart, benchmark or verification suite was run by this planner. All execution/approval gates in [exit criteria](exit-criteria.md) remain open.

## Evidence Log

| Item | Reference | Notes |
| --- | --- | --- |
| Workflow/template inspection | [AGENTS.md](../../../AGENTS.md), [agents](../../development/agents.md), [six templates](../../templates/) | Six completed template-derived files authored only under this new plan folder; disclosed Azure fallback after Muse402 |
| Read-only local dirty inventory | `git status --short`, 2026-10-30 planner inspection | Existing credit/routing/tests/canonical docs changes and pricing-estimation-503/responses-request-limit plans are USER WORK; no writes there |
| Latest production outcome | [Pricing packet](../pricing-estimation-503/production-packet.md), [evidence](../pricing-estimation-503/evidence.md) | Historical deployed memory/one pricing-20261029;22backends/14pools/fouraccounts; actual live rediscovery still required |
| Historical Table gap | [Real inference](../table-real-inference/evidence.md), [metadata correction](../table-write-metadata/evidence.md) | Original failed/ambiguous nonstream and consumed budget remain immutable; supplemental2stream settlements pass, full current nonstream/restart remains open |
| Existing infrastructure proof | [Two replicas](../table-two-replica/evidence.md), [cross-RG](../table-existing-cross-rg/evidence.md), [IaC](../../../infra/README.md) | Synthetic historical evidence only; prefer discovery/reuse before new resources |
| Financial migration semantics | [Shared credit operations](../../operations/shared-resource-credit.md), `src/foundry_router/credit.py` | Accounts nonadditive; conservative retained intent/recovery; current estimator follows configured intake and bounded feature serialization |
| Intake/scaling inspection | `src/foundry_router/api/common.py`, `infra/modules/containers/router.bicep` | Current intake builds full bytearray/decoded JSON; current static0.25vCPU/0.5GiB; raising limits alone does not prove resource safety |
| Quota/metrics prerequisite | [Quota evidence](../distributed-quota-accounting/evidence.md), `src/foundry_router/state/quota.py`, [metrics evidence](../metrics-aggregation/evidence.md) | Locally implemented/verified; Pacific-day/input-TPM semantics and bounded row are not automatic Azure policy; deployed provider/aggregation gates remain open |
| Test/verification references | `pyproject.toml`, `tests/unit/test_table_real_verification.py`, existing Table/quota/intake/main tests, [testing](../../development/testing.md) | Inspected, not executed; fresh source tests/coverage/Docker required |
| Official Responses payload wording | [Microsoft Learn](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/responses), read2026-10-30, image-input section | Up to50images; individual image and combined prompt/images under512MB. Content bound, not a proven512MiB wire cap; file inputs distinct. Other Azure operations/wire/platform limits need research |
| Conditional review tooling | `scripts/quality/sonarqube-scan.sh` glob absent; [deep-review prompt](../../../.agents/prompts/deep-review.prompt.md) present | Sonar absent N/A at authoring, recheck later; independent deep review still mandatory, not performed |
| Proposed budget/scale judgement | [Activities](activities.md), [risks/open decisions](risk-register.md) | Fresh aggregate USD1 reserved local estimate/16attempts, text128output/zero retries; min1/max3 after gates,30minute synthetic scale exercise; no actions yet |
| Independent plan/candidate/packet verdicts | Pending | Coordinator must obtain separate-session reviews; planner does not self-approve |
| Plan relative-link check | All six new Markdown files, local read-only Python check | No broken relative links; this is documentation validation only, not runtime verification |

## Coordinator preflight, 2026-10-30

- Fresh `.venv/bin/python -m pytest --cov=src/foundry_router --cov-report=term-missing`: **2,887 passed, 21 skipped, 90.46% runtime coverage**, 57.97 seconds. Full output retained privately as `table-production-baseline-pytest.log`. This is baseline verification, not candidate or Azure acceptance.
- Ruff check: all checks passed. Ruff format check: 1,064 files already formatted. Mypy: no issues in 76 source files. Sonar script absent (N/A).
- All 78 runtime/dependency/build files in the deployed pricing release's source manifest still match their SHA-256 pins; no runtime rebuild is required solely for isolated Table validation.
- Live read-only discovery found the existing isolated Table real-inference app and hardened shared storage with its historical credit/health tables. Readiness returned HTTP200 with `ready=true` and `state_store_reachable=true`. No paid calls or rows were changed.
- Production remains the immutable pricing release, memory, one replica, 0.25 CPU/0.5 GiB. Its identity has registry/vault access but no Table data grants. Production environment has only the Consumption workload profile.
- [Independent phased plan review](plan-review.md) approves Phase0 and conditionally approves Phase1; exact packet must close isolated old/new writer overlap. Later payload/scale decisions do not block safe Table/one migration.
- Sole developer owns only the new isolated acceptance harness/tests and Phase1 packet. Coordinator owns this evidence file. Existing user changes and historical consumed ledgers are preserved.
- Exact deployed Linux/amd64 image pulled by immutable digest. With networking disabled, runtime imports for main, Table credit/health, quota, Azure SDK and aiohttp passed. Direct comparison of all **76 runtime Python file hashes inside the image** against the working tree found zero mismatches.
- Dedicated temporary Azurite Table service: **15 integration tests passed** in 1.52 seconds. The task-owned emulator was then stopped; unrelated containers were not touched.
- Read-only resolved isolated backend configuration uses one dedicated Foundry resource absent from production's configured host set. G1's fresh approved budget is separate from production's four canonical account allocations; exact packet must bind that disjointness before dispatch. Existing synthetic test balances are not provider wallet balances.
- Azure payload research independently reviewed and corrected: no unresolved Critical/Major. [Research](azure-payload-research.md) and [review](azure-payload-research-review.md) are committed as `6b8d5c2`; research approval is not implementation or deployment approval.

## Isolated execution and recovery gate

- The verified acceptance harness was committed as `389401c`; drain/secret-reference safeguards followed in `eaab2e9`. Final focused selection: **95 passed, 97.10% harness coverage**. Full selection: **2,982 passed, 21 skipped, 90.46% runtime coverage**. Ruff/format/Mypy passed. Runtime image/source files remained unchanged.
- [Exact review](phase1-exact-packet-review.md) approved packet SHA-256 `721fc9be3e5a862741e3c71eaa327dc8c0e153c789ee0a17029af4ee13a9e8de`, with four isolated cases and USD0.01792 aggregate reserved local estimate. Staged fenced/min1 completion was explicitly accepted; production mutation was not part of this packet.
- One `apply` invocation **stopped**, returning `Fence denial unproved`, immediately after setting the isolated app's deny-all ingress. It did **not** reach old-writer deactivation, image promotion or any inference slot. The execution and original program ledger remain consumed/immutable; no replay occurred.
- Post-failure read-only inspection confirmed provisioning succeeded, deny-all ingress present, original corrected test image/revision and min0/max1 retained. Public readiness returned **403** after propagation. Replica-local diagnostics confirmed the **same old process**, **unchanged canonical account state**, **zero case-consumption markers** and **no old-writer stop marker**. These are point-in-time observations, not a claim that min0 prevents later scale-to-zero.
- Production remains unchanged, memory/one. No provider inference was dispatched by the failed isolated run.
- A [fresh recovery plan](g1-fence-recovery/activities.md) and [independent review](g1-fence-recovery/plan-review.md) authorize implementation only. Recovery must use a new approved identity, bounded ingress-propagation checks and only the original verified unstarted slots; exact execution approval remains open. The production harness author was paused and released source ownership for recovery.

## Execution evidence to append later

Record each phase separately with actual UTC dates, current source/image/helper hashes, reviewed packet verdict, exact redacted scope, private artifact hashes, attempt count/reserved/known/uncertain estimates, configuration/ingress preservation and real versus synthetic coverage. Keep IDs, secret values, prompts, images and model outputs out of committed evidence. A missing/failed transport/result is an open gate. Close production restoration and observed worker transitions explicitly; never relabel planned actions as deployed.
