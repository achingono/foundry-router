# Credit accounting correction verification evidence

Status: local code verification **Passed**; independent contextual implementation review remains pending. No Azure resource, secret, billing configuration or inference call was changed by this verification.

## Automated checks

| Check | Result |
| --- | --- |
| Focused credit accounting/shared-credit tests: `.venv/bin/python -m pytest tests/unit/test_credit_accounting_correction.py tests/unit/test_shared_resource_credit.py -q --disable-warnings` | **Passed:** 90 passed |
| Full applicable suite with coverage: `.venv/bin/python -m pytest tests/unit/ tests/integration/ -m 'not docker and not azurite' -q --cov=src/foundry_router --cov-report=term-missing --cov-fail-under=80` | **Passed:** 2,805 passed, 3 skipped, 19 deselected; 90.39% total coverage. Changed core modules: credit 93.24%, config 90.52%, Table 87.33%, admin 95.77%, metrics 100%. |
| Ruff lint: `.venv/bin/ruff check .` | **Passed:** all checks passed |
| Ruff formatting: `.venv/bin/ruff format --check .` | **Passed:** 1,017 files already formatted |
| Mypy: `.venv/bin/mypy src/` | **Passed:** no issues in 73 source files |
| Azurite distributed state: `.venv/bin/python -m pytest tests/integration/test_azurite_distributed_state.py -q -m azurite --disable-warnings` with local Azurite and localhost network permission | **Passed:** 15 passed. Includes settlement/recovery serialized-counter checks against real Table SDK behavior. |
| Native Docker build | **Passed:** `docker build -t foundry-router:credit-accounting-correction .`; local arm64 image built. |
| Production-target Docker build | **Passed:** `docker build --platform linux/amd64 -t foundry-router:credit-accounting-correction-amd64 .`; image inspection reported `linux/amd64`. |
| Container health | **Passed:** Linux/amd64 candidate started with synthetic configuration; `GET /health/live` returned `{"status":"alive"}`. Test container was stopped afterward. |
| Documentation links and diff hygiene | **Passed:** relative Markdown links across 20 changed/new documentation files resolved; `git diff --check` clean. Secret-pattern review found only expected documentation examples/instructions and synthetic test credentials. |
| SonarQube | **Not applicable:** `scripts/quality/sonarqube-scan.sh` is absent. |

The first full-suite attempt ran inside the network-restricted sandbox. It hit localhost TCP loopback failures and was interrupted; that run is not counted as passing evidence. The complete run above was repeated with localhost network permission and passed. The initial sandbox-only Azurite attempt skipped; the 15-test pass above used the accessible local emulator.

## Scope notes

- The full suite deselected 19 tests by the Docker/Azurite markers; all 15 applicable distributed-state Azurite tests were run separately and passed. The CI pipeline's marked quota and cost-ceiling Azurite suites were not included in this targeted run.
- The implementation adds optional cached-input usage pricing and memory/Table canonical settlement/recovery counters. It does not set production monetary configuration or establish provider cached prices.
- Plan approval is recorded in [plan review](plan-review.md). The separate contextual implementation deep review and concrete production packet review/deployment remain open gates.
