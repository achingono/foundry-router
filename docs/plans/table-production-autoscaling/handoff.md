# Handoff: production Table state, Foundry payloads and autoscaling

## Status and authorized objective

**Paused. The objective is not complete.** The latest developer subagent was cancelled.
This document authorizes no execution by itself. When assigned to resume, the next agent
should finish the already-authorized objective in this order:

1. Validate current-release Table-backed inference and restart persistence.
2. Migrate production to Table state with one worker/replica and preserved credit estimates.
3. Implement safe intake supporting Azure Foundry payloads, without arbitrary router byte
   caps below upstream support; leave unknown model/wire constraints upstream-owned.
4. Validate and enable bounded horizontal autoscaling.

The user approved judgement-based inference testing costs and requested incremental commits.
Ignore other providers for new feature/testing scope, but **preserve their configuration,
credentials, capabilities and all four production accounts**. Do not delete their pools.
Do not ask what to do next; ask only for an actual missing credential, permission, decision
or manual intervention that cannot be resolved within the authorized scope.

Follow [AGENTS.md](../../../AGENTS.md) and [agent workflow](../../development/agents.md),
with one source/test writer, independent review and actual verification evidence. This
handoff-writing action does not resume Azure operations or launch agents.

## 1. Last verified live state — refresh before action

| Item | Last observed state |
| --- | --- |
| Production app | `foundry-router-production`, resource group `rg-foundry-router-prod-eastus` |
| Production revision | `foundry-router-production--pricing-20261029` |
| Production storage/scaling | **Memory**, min1/max1, 0.25 CPU / 0.5 GiB; readiness HTTP200/ready=true |
| Original incident | Production still has no request-size override: default **2 MiB** remains; the 413 is not fixed |
| Isolated app | `foundry-router-table-real-261008`, resource group `rg-ml-studio` |
| Isolated current revision | `foundry-router-table-real-261008--0000003` |
| Isolated storage/scaling | **Table**, min1/max1, current production image, retry0 |
| Isolated worker proof | Four revisions total; one active/ready current worker; three old inactive revisions with zero workers |
| Isolated finance | Two canonical account maps match the pre-promotion drained state; current debit/recovery fields present; zero reservations |
| Isolated ingress | **Deny-all**, public readiness HTTP403; original ingress/min0 restoration is still outstanding |
| Controlled inference | **Zero of the four original validation slots started** at last inspection |
| Production suitable storage | Existing hardened `frcrossrg261004` in `rg-shared-eastus`; HTTPS-only, TLS1.2, shared keys disabled |
| Permissions | Operator scoped table-create/role-assignment-write checks passed; production identity still needs scoped Table data grants |

The test app remains always-on at min1 and incurs compute charges while paused. Do not
claim it is cleaned up, or reopen it without the reviewed restoration procedure.
These are historical observations, not guarantees about the next session's live state.
Discover subscription/resource/client/principal IDs from Azure and private bindings;
do not invent them or hard-code credentials in repository files.

Immutable current image digest:

```text
sha256:36d453f80c2fd8af990eab43f9030c3da1e0992b247aaaf742b31aff9c3bcea4
```

All 76 runtime Python files inside that Linux/amd64 image matched the working source;
78 runtime/dependency/build inputs matched its release manifest. Do not rebuild merely
to repeat unchanged Table acceptance. Runtime changes later require a new verified image.

## 2. Why earlier runs stopped — do not repeat these mistakes

The Table runtime already existed. Most delay came from increasingly elaborate operator
automation whose mocks missed Azure lifecycle behavior:

- Ingress changes propagate asynchronously: observe the desired public status under a
  **total deadline**, rather than assuming an immediate403/200.
- Long Container Apps exec commands returned WebSocket404; the compressed diagnostic
  command succeeded. Keep credentials out of command arguments and console captures.
- Installed Azure CLI updates added empty `value` entries to secretRef-only environment
  entries. Use validated, narrowly scoped REST template updates preserving references.
- API `2024-03-01` rejected preserved `cooldownPeriod`/`pollingInterval` fields. The same
  proposed template validated successfully with supported API **`2025-01-01`**.
- The actual rejection was HTTP400 ProblemDetails with **no provider error code**.
  Never invent `InvalidRequestContent` or service-generated operation IDs.
- `revision list` defaults to active revisions. Use **`--all`** and enumerate each revision's
  replicas; otherwise an inactive draining worker can be missed.
  The frozen original/recovery helpers did not do this automatically. Use the continuation's
  `AllRevisionsAzure` wrapper or an explicitly corrected inventory reader, not those defaults.
- With all revisions stopped, the endpoint returned404 despite configured deny-all;
  distinguish no active route from a live403. Never accept public200 as a fence.
- During successful promotion, the **approved new revision** briefly had an inactive worker.
  Under a verified fence, classify owned current-version transitions separately from old
  or unapproved workers. Finish only with one healthy active revision/ready worker.

The image promotion **succeeded**. Do not redeploy it, reactivate old revisions, rerun old
apply commands or build another deployment recovery framework just to execute four calls.
See [execution evidence](evidence.md) and the historical review directories for details.

## 3. Preserve working-tree and private material

Inspect `git status`, current instructions and existing tests before editing. Ten task
commits were made, most recently `e9b08c0`; the runtime source changes listed below are
pre-existing user/deployed pricing work, **not disposable task changes**:

```text
src/foundry_router/credit.py
src/foundry_router/routing/__init__.py
tests/unit/test_credit.py
tests/unit/test_main.py
docs/api/index.md
docs/configuration/index.md
docs/decisions/requirements-traceability.md
docs/operations/observability.md
docs/plans/pricing-estimation-503/
docs/plans/responses-request-limit/
```

Do not reset, revert or indiscriminately stage that work. Commit only reviewed task-owned
increments. The older `responses-request-limit` plan is not authority for a blind512MB rollout.

### Cancelled, uncommitted finish draft

These local files exist but are **not independently verified or execution-approved**:

| File | SHA-256 at cancellation/handoff |
| --- | --- |
| `scripts/quality/table_production_acceptance_finish.py` | `0e465b35aa6b41db8427d2a98b72267ee34cf22e1a10376f4b82fb61ed6f777c` |
| `tests/unit/test_table_production_acceptance_finish.py` | `1b1a8519d20da5eeb8e0f6e46fdaa0fc01eb05ba1c2ca2e39411f5d0673a3b58` |
| `docs/plans/table-production-autoscaling/g1-ready-finish/packet.md` | `0c58c4e68a5717c315109ee4052cfc16574b0f3ec0a7ac708f8b57f682d24922` |

The draft packet reports41 mocked tests/98.91% coverage, but cancellation prevented a
final handoff. Rerun checks; do not promote that assertion to independent verification.
Latest **independent** full verification before this draft: **3,086 passed, 21 skipped,
90.46% runtime coverage**, plus Ruff/Mypy. Fifteen real Azurite tests passed separately.
Sonar script was absent: N/A, not a scan pass.

### Local-only artifact locator

On the original machine, define the approved private base directory:

```text
/private/var/folders/yb/v29g2l750ms2bky383fkb6j00000gn/T/opencode
```

| Directory under that base | Purpose |
| --- | --- |
| `table-prod-g1-20261030-e/` | Original approved packet, consumed program ledger, old-drained/stop/absence/proposal/promotion markers; original slot identities |
| `table-prod-g1-recovery-20261030-a/` | Consumed cold/fence recovery and retained API2024 failure |
| `table-prod-g1-continuation-20261030-d/` | Consumed API2025 continuation, successful promotion followed by transitional-worker check failure |
| `table-prod-g1-ready-evidence-20261030-a/` | `ready.json`, last ready/financial/worker evidence; SHA `aa820b62968cc4c44ba8c28589e697c4cd7320faecf882de9aba0ade435e5fbc` |
| `table-g1-api-validation-20261030-a/` | Actual provider/rejection/validation/what-if captures, including truthful null error code and raw-template hash domain |

Earlier attempts/prepares remain historical, not reusable execution identities. The four
original slots reserve **USD0.01792** inside an existing **USD1/16-attempt** controlled
program, max64 reported input/max128 output tokens per original case. These are local
reserved-estimate bounds, not invoice guarantees. Preserve every consumed/failed record;
never recreate the program as a new allocation or recycle a started/unknown slot.

These files and the uncommitted drafts are **not supplied by a fresh clone**. If missing,
obtain the originals or establish a separately reviewed fresh-state continuation. Do not
reconstruct mutable ledgers, approvals, private IDs or consumed history from prose.

## 4. Next action: finish isolated acceptance, without redeployment

Use the [ready-only plan](g1-ready-finish/activities.md) and
[independent plan verdict](g1-ready-finish/plan-review.md).

1. Take source ownership and audit the cancelled draft. Reuse existing validated helpers;
   do not add new layers or invoke any historical `apply` entrypoint.
2. Reinspect live current image/configuration, secret versions/value hashes, all revisions
   and workers, fence, canonical finance/cycle state and original slot markers. Bind a
   **fresh** ready capture if a platform restart changed process/generation. Financial or
   cycle drift requires read-only reconciliation and an independently reviewed amendment,
   not forced equality, stale seed reload or a deployment replay.
3. Verify the finish-only scope: executor Allow, four original unstarted calls, final DENY,
   quiet drain and one current-revision restart. No image/table/role/seed/pool mutations.
4. Run focused coverage and full repository checks. Obtain independent contextual review,
   then fresh hash-bound private preparation and **exact executable approval** before any
   ingress mutation, paid dispatch or restart. Prior approvals do not approve the draft.
5. Execute each original slot once, consuming its marker before HTTP. Require nonstream
   and stream completion/usage for both selected Azure deployments, price-matched single
   debit/counter deltas, zero reservations and financial continuity between every case.
   Stop on ambiguity or failure; never retry/substitute/increase limits silently.
6. Fence/drain and restart the current revision once. During bounded observation, tolerate
   only owned current-revision/current-image transitions; reject old/unapproved workers.
   Require actual container/process replacement, final one-ready-worker state, unchanged
   persisted balances/counters/configuration and live403. Record truthful result links.
7. Review and execute isolated cleanup: restore **exact original ingress and min0** from
   the original prepared record, preserving current Table state/image. Verify it; min1
   cost and ingress restoration are not automatically closed by finish success.

If the original small-output cases cannot complete, use a reviewed cost/output/slot
amendment within the user-authorized scope. Do not rewrite already-started history.

## 5. Then migrate production to Table/one

Read [migration mechanics](table-migration-mechanics.md), its
[review](table-migration-mechanics-review.md) and the [phased plan](activities.md).
The migration does **not** need to wait for payload/autoscaling implementation.

Three unfinished production drafts were preserved outside the repository under the private
base. Restore them to their intended paths only after checking ownership and hashes:

| Private filename | Intended repository path | SHA-256 |
| --- | --- | --- |
| `table-production-migration-paused-b.py` | `scripts/quality/table_production_migration.py` | `9ed39af75d289e4d9e039dae004411078c673ab321d81973fe7b82f020c2c23d` |
| `test-table-production-migration-paused-b.py` | `tests/unit/test_table_production_migration.py` | `ea5dc616163ba99d898178464ca12cae70fc04ad47b77a099392ec9202db5b5f` |
| `table-production-migration-paused-b.md` | `docs/plans/table-production-autoscaling/phase2-packet.md` | `dacb2e987cf60d818b0adbe035434bd516b4947f364405da91a8283280a7a958` |

Do not execute private copies as if their relative imports/root paths were configured.
They are **unfinished**: last mock run23 passed/9 failed,35.77% coverage. Principal failure
was settings deep-copy of `mappingproxy`; use validated raw configuration rather than
blindly copying frozen settings. Fix types/tests, stale placeholder documentation, API2025
selection, `--all` and the new actual G1 result-chain prerequisites before review.

Required production procedure:

- Rediscover/bind current22-backend/14-pool/four-account roster, aliases, prices, reserves,
  cycles, effective pinned secrets, original ingress and immutable image; refresh counts.
- Create only dedicated production credit/health tables on suitable existing storage,
  with production managed identity granted data access **at those table scopes**. Verify
  hardening, role propagation and whole-table emptiness before stopping production.
- Independently approve the exact footprint/executable. Fence public intake, observe denial,
  drain all requests/reservations/background writers and capture fresh same-process
  **canonical group** estimates. Floor seeds conservatively; never sum backend mirrors.
- Stop/exclude all memory writers before starting the successor. Use fresh version-pinned
  seed references and Table create-if-absent initialization; no stale memory seed replay.
  Current implementation starts a **new counter lifetime at0**; retain old history separately
  and never claim historical cumulative-counter continuity.
- Use supported template-only REST updates preserving secretRefs; do not repeat the known
  CLI/API/lifecycle mistakes. Verify all four rows, cycles/reserves/seeds, zero reservations,
  sole healthy Table/one worker and unchanged original configuration.
- Perform bounded representative production acceptance across the two active Azure accounts.
  **Retry0 does not disable failover.** If using temporary single-candidate acceptance pools,
  independently approve that amendment, preserve original pools and restore the exact
  original model/pricing/retry bundle before public reopening. Do not invent a backend-selection
  request header or assume weighted routing proves account coverage.
- Prove production restart preserves all four balances/counters. Restore exact original
  ingress only after final original-roster/configuration and readiness checks.
- On failure, inspect persisted state and retain the safest fence. Never automatically
  reactivate an old memory revision; memory recovery requires fresh Table-derived estimates
  after all Table writers are drained/frozen. Preserve tables and uncertain liabilities.

## 6. Payload support and autoscaling — still Planned

Use the [reviewed Azure payload research](azure-payload-research.md) and
[review](azure-payload-research-review.md); reread current official sources.

- Responses documents512MB prompt/image content, **not a JSON wire cap**. Base64 alone
  expands512,000,000 bytes to682,666,668 bytes before JSON overhead. Do not blindly set
  `512 MiB`, reuse the old unimplemented plan, or remove the cap while buffering without
  aggregate memory protection. PDF, embeddings, Anthropic and MAI limits are distinct.
- Leave upstream token/context semantics upstream-owned; do not invent token-to-byte caps
  or expand tokenizers/provider feature support merely to fix intake. Support ordinary
  upstream-sized requests with measured resource capacity; a perpetually undersized lane's
  busy response is not a substitute for lifting the old cap.
- Benchmark the simplest bounded full-JSON path first. Use private spooling/incremental
  parsing only if measurements require it. Cover base64/Unicode, model-last/chunked intake,
  concurrent workloads, cancellation, slow streams, health responsiveness and cleanup.
  Preserve auth/redaction, strict JSON/depth protections, conservative credit estimation,
  media accounting and SSE/no-retry-after-output semantics. Check hidden estimator/adapter
  bounds as well as the2MiB intake limit; preserve non-Azure behavior.
- Select a supported static CPU/memory pair from measured peak memory/concurrency, not guesses.
  Container Apps has **horizontal** autoscaling, not native vertical autoscaling; more replicas
  do not make a single oversized allocation safe.
- Before scale-out, verify current quota policies, shared credit/health admission/settlement,
  fail-closed storage behavior and operational aggregation. The existing Table quota design
  is Google-oriented: do not fabricate Azure/RPD semantics or assume it is required when
  no local policy is configured. Whole-app scaling also affects preserved other providers.
- Stage bounded min1/max2 then max3 with benchmark-derived HTTP/KEDA thresholds. Prove actual
  scale-out/in, native Azure settlement on at least two actual workers, persistence and
  safe shutdown. Use synthetic/no-provider load for autoscaler exercises, not a paid flood.
  Verify real OTLP aggregation or an independently reviewed platform/logs/Table alternative;
  load-balanced process-local `/metrics` is not an aggregate, and shared ledger views are nonadditive.

## 7. Verification, final evidence and stop rules

Prefer repository `.venv/`; focused tests then full coverage≥80%, Ruff lint/format,
Mypy, applicable Docker/Azurite/Bicep validation/finite what-if, conditional Sonar and
independent deep review. Operator sibling imports require the documented type-check path:

```bash
.venv/bin/python -m pytest --cov=src/foundry_router --cov-report=term-missing
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
.venv/bin/python -m mypy src
```

For relevant operator files use `MYPYPATH=src:scripts/quality` and the packet's explicit
Mypy options. Do not include unfinished private drafts in a candidate verification scope.
An unchanged runtime image can reuse justified build evidence; runtime changes cannot.

Final completion requires **actual** production Table state, preserved finance/restart
evidence, supported Azure intake/resource benchmarks, observed bounded autoscaling,
operational visibility, exact ingress/configuration restoration and isolated cleanup.
Update API/configuration/security/operations/architecture/traceability, validate relative
links, review secrets/claims and make incremental reviewed commits. Label deployed, local,
synthetic, native, unverified and Planned scope precisely.

**Never** reset/discard user work; replay a consumed operation; refund unknown/started
liability; silently increase budgets; fabricate IDs/caps/approvals; expose keys/prompts/outputs;
or describe a passing mock/full suite as a live acceptance pass. If private material,
credentials or permissions are genuinely unavailable, report the precise blocker and stop.

Planning estimate at pause: isolated finish/cleanup1–3 hours; Table/one migration4–8 hours;
payload implementation/benchmarks1–3 days; scale-out/observability acceptance0.5–2 days.
These are rough focused-engineering estimates, not guaranteed turnaround. Prioritize the
Table/one outcome and avoid further disproportionate recovery-framework construction.
