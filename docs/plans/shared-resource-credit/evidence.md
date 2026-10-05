# Evidence

## Latest remaining-Major follow-up verification

All three follow-up fixes are **Implemented**: **444 tests passed**, **90.14% coverage**, all
**14 Azurite tests**, Ruff/format/mypy and Docker build passed. See
[follow-up evidence](follow-up-evidence.md). Earlier 428/399-test results below are historical.
Final follow-up link validation: **131 local links in 21 feature Markdown files**, all valid.

## Latest recovery verification

The independently approved five-Major recovery amendment is **Implemented**: **428 tests passed**,
**90.08%** coverage, all **11 Azurite tests**, Ruff/format/mypy and Docker build passed.
See [recovery evidence](recovery-evidence.md) for exact commands, fault scope and remaining gates.
The original 399-test results below are historical baseline evidence, not the latest verification.
Final documentation validation: **122 local links in 19 feature Markdown files**, all targets exist.

| Item | Reference | Notes |
|---|---|---|
| Operator scope | Current session | Six matching models in each of two resources; shared accounting selected; placeholder input file requested |
| Baseline | d12b13f | Real Responses fixes and evidence committed |

## Implementation — 2026-10-04

Status: **Implemented** (runtime and local verification); production deployment **Planned**.
Approval source: operator supplied the approved plan and the reviewed contract clarifications in
`activities.md`. Independent implementation review will follow; the implementing-session
[contextual review](review.md) records its scope and addressed findings.

### Files and behavior

- `src/foundry_router/credit_groups.py`: safe namespace, stub-compatible membership, one-pass
  aliases, coherent metering and reconciliation prevalidation/coalescing/conflict rejection.
- `config/__init__.py`: optional `BackendConfig.credit_group`, backend-ID default during Settings
  parsing, safe IDs and canonical group keys for unchanged credit-map variable names.
- `credit.py`, `state/table.py`: unique group initialization and shared balance/reservation state,
  context/scalar compatibility, captured ownership, pending live-change guard and same-object sync
  retry. Default backend partitions and legacy `backend_id` properties remain compatible.
- `state/table.py`: strict pending/balance parsing and typed finalization read/transaction/conflict
  failure; confirmed absent/finalized is idempotent. Reconciliation storage failures mark attempts
  failed; updates are atomic per group, not across groups.
- `routing/`, `api/common.py`, `forwarding/`: failed release prevents subsequent selection/egress;
  failed settlement never becomes a free release; independent quota/metrics cleanup, including
  quota admission errors/cancellation and terminal streaming usage inspected before yielding.
- `api/routes/{health,admin}.py`, `main.py`, `metrics/`, `reconciliation/`: unique routable metered
  readiness/Table probes, canonical admin groups and metric, compatible backend views/group field,
  unique reconciliation count with legacy count alias.
- `tests/unit/test_shared_resource_credit.py`: 56 cases across memory/Table covering namespace,
  combined model capacity, twelve-backend/six-pool/two-account topology, ownership, legacy defaults,
  reconciliation, same/different-group failover, release/settlement failure, quota cancellation,
  streaming cancellation and cleanup, readiness and canonical diagnostics.
- Updated existing corrupted-reservation/outage expectations in `tests/unit/test_state.py` and
  `tests/integration/test_azurite_distributed_state.py`; added real SDK/Azurite cross-model contention,
  restart, settlement and coalesced reconciliation verification.
- Canonical configuration, architecture, routing, API, observability, operations, traceability and
  documentation hub updated; [migration guide](../../operations/shared-resource-credit.md) added.

### Verification

| Check | Exact command / result |
| --- | --- |
| Initial focused compatibility suite | `.venv/bin/python -m pytest tests/unit/test_credit.py tests/unit/test_state.py tests/unit/test_table_concurrency.py tests/unit/test_main.py tests/unit/test_distributed_wiring.py tests/unit/test_api_common.py tests/unit/test_forwarding_stream.py tests/unit/test_metrics.py tests/unit/test_config.py tests/unit/test_reconciliation.py -q` — 237 passed |
| Focused shared-credit/Table/Azurite verification | `.venv/bin/python -m pytest tests/unit/test_shared_resource_credit.py tests/unit/test_state.py tests/integration/test_azurite_distributed_state.py -q --disable-warnings` — 109 passed at that checkpoint; later additions included in final full suite |
| Final full suite including Azurite | `.venv/bin/python -m pytest -q --disable-warnings --cov=foundry_router --cov-report=term-missing --cov-fail-under=80` — **399 passed**, **89.80%** coverage, 46.96s; all 9 Azurite tests executed, no skips |
| Ruff | `.venv/bin/ruff check src tests` — passed |
| Formatting | `.venv/bin/ruff format --check src tests` — 45 files already formatted; edits applied only via apply_patch |
| Types | `.venv/bin/mypy src` — no issues in 24 source files |
| Patch whitespace | `git diff --check` — passed |
| Documentation links | Temporary feature-scoped checker — **113 local links in 17 Markdown files**, all targets exist |
| Docker | `docker build -t foundry-router:shared-resource-credit .` — passed, Python 3.12 runtime with Azure extras; local manifest `sha256:4b79e8155c06367b8009c36e245b07ea8a740b29b3ccf77b0ef677b1d6593c7d` |
| Sonar | `scripts/quality/sonarqube-scan.sh` absent; not run |

Azurite was started in a session-owned Docker container using
`docker run -d --rm --name foundry-router-shared-credit-azurite -p 127.0.0.1:10002:10002 mcr.microsoft.com/azure-storage/azurite azurite-table --tableHost 0.0.0.0 --skipApiVersionCheck`.
Tests used isolated random tables and real Azure SDK ETag transactions. Local test Python was
3.14.7; emitted dependency deprecation warnings did not fail checks.
The session-owned Azurite container was stopped with
`docker stop foundry-router-shared-credit-azurite` after verification; `--rm` removed it.
Final feature diff was reviewed for ownership/cleanup transitions, unsupported deployment claims
and credentials; test-only example credentials are the only new credential literals.

### Remaining gates

- Independent implementation review pending, as requested.
- Operator-owned `infra/production-inputs.local.json` null completion pending; file untouched.
- No Azure production deployment, configuration overwrite, commit or push performed.
- Production remains memory-backed with one replica. Real shared-credit inference, production
  provider admission/failure traffic and multi-worker metrics aggregation remain unverified.
- Deployment-time discovery, redacted credentials and actual resource-level pricing/cycle/remaining
  values must be completed before any production rollout. No placeholder estimates were deployed.
