# G1 API2025 continuation verification

**Status: Partially implemented — current M4 candidate passed local mocked
verification; Azure execution gates remain.** Updated 2026-10-30. This is local
verification of the [continuation packet](packet.md), [operator](../../../../scripts/quality/table_production_acceptance_continue.py),
and [focused tests](../../../../tests/unit/test_table_production_acceptance_continue.py).
It is not an execution approval or evidence of Azure acceptance.

## Final M4 full-revision inventory verification

The current candidate is source-frozen at these exact SHA-256 values:

| File | SHA-256 |
| --- | --- |
| Continuation operator | `a2b3e20c24141528ff92560c9675eebb6289a29339bb51257ea16566724280ee` |
| Continuation tests | `c912b9f8eaa93f1066819999cc8e19a8897d130a528ebb5b5d240708375b1191` |
| Continuation packet | `43fe06467626fbe9ceab6898b8b87966d098c9a8be3bc154ac338b8d0b669677` |
| Frozen original G1 operator / tests | `701cca098ce005703cc97d298adde7c7072e61ce8bf233b0f941c815ffa7e922` / `04b79e5fea57bb527dbf4015d401aff59697069dfa3c7fc2aee66851585e2a8b` |
| Frozen recovery operator / tests | `e3c47d6c7b7634c5578032df06795d4363205804f475d58d80f4560e7c8b6f45` / `762df8cb9e932ada219c1afe6b7b709c9e2dc4438cde732bcf6a5b041ef1f887` |

| Check | Actual final result |
| --- | --- |
| Focused continuation tests | **68 passed**, 15 dependency deprecation warnings, 2.02 s |
| Focused operator coverage | **99.64%** — 275 statements, 1 missed |
| Full repository pytest | **3,086 passed, 21 skipped**, 8,969 warnings, 58.70 s |
| Full `src/foundry_router` coverage | **90.46%** — 11,472 statements, 1,095 missed |
| Ruff lint | Passed for `src`, continuation operator and focused tests: “All checks passed!” |
| Ruff format | Passed for the same paths: “78 files already formatted.” |
| Mypy source | `.venv/bin/mypy src` passed: no issues in 76 source files |
| Mypy continuation operator | `MYPYPATH=src:scripts/quality .venv/bin/mypy scripts/quality/table_production_acceptance_continue.py` passed: no issues in one file |
| SonarQube | N/A — `scripts/quality/sonarqube-scan.sh` is absent |

The continuation-local `AllRevisionsAzure` wrapper copies CLI argument lists
and appends `--all` to every `revision list` call, including revision-list calls
made through inherited G1/recovery helpers; it leaves other commands and frozen
helper bytes unchanged. Tests verify target/subscription argument preservation,
that the original list is not mutated, and that the stopped proof inventories
exactly three inactive revisions with zero workers. The hidden-inactive-worker
regression is tested at prepare, apply, and immediately after promotion: an
ordinary active-only list conceals the worker, but the full-inventory guard
refuses before any case marker; prepare/apply refusal occurs before mutation, and
the post-promotion case stops after the one fake PATCH. Tests run against mocks
and temporary artifacts only.

Focused and full logs are private mode-600 captures in the approved temporary
directory; coverage data is outside the repository. Commands run:

```text
COVERAGE_FILE=<approved-temp>/continue-m4-final-focused.coverage \
  .venv/bin/python -m coverage run --source=scripts/quality -m pytest \
  tests/unit/test_table_production_acceptance_continue.py
COVERAGE_FILE=<approved-temp>/continue-m4-final-focused.coverage \
  .venv/bin/python -m coverage report -m \
  --include=scripts/quality/table_production_acceptance_continue.py
COVERAGE_FILE=<approved-temp>/continue-m4-final-full.coverage \
  .venv/bin/python -m pytest --cov=src/foundry_router --cov-report=term-missing
.venv/bin/ruff check src scripts/quality/table_production_acceptance_continue.py \
  tests/unit/test_table_production_acceptance_continue.py
.venv/bin/ruff format --check src scripts/quality/table_production_acceptance_continue.py \
  tests/unit/test_table_production_acceptance_continue.py
.venv/bin/mypy src
MYPYPATH=src:scripts/quality .venv/bin/mypy \
  scripts/quality/table_production_acceptance_continue.py
```

Current private capture SHA-256 values:

| Capture | SHA-256 |
| --- | --- |
| `/private/var/folders/yb/v29g2l750ms2bky383fkb6j00000gn/T/opencode/continue-m4-final-focused.log` | `112e36b489b092c93ff565a191b495cbac072bccf71bcd54090f25708a02d44d` |
| `/private/var/folders/yb/v29g2l750ms2bky383fkb6j00000gn/T/opencode/continue-m4-final-full.log` | `8bcb77cbe7910d2b16c1c27c07d85677717a084a96c978e8d82a175429b488a4` |
| `/private/var/folders/yb/v29g2l750ms2bky383fkb6j00000gn/T/opencode/continue-m4-final-ruff-check.log` | `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18` |
| `/private/var/folders/yb/v29g2l750ms2bky383fkb6j00000gn/T/opencode/continue-m4-final-ruff-format.log` | `1a3c6aa46d7f5260e23740995cfa3cf8617f1bd5d18465e940eb76f39be45866` |
| `/private/var/folders/yb/v29g2l750ms2bky383fkb6j00000gn/T/opencode/continue-m4-final-mypy-src.log` | `b1d14a638cdcd6b7a7d5368e3cc2ca927b3e1f1b4e26cbe9b1844d7698aabdf2` |
| `/private/var/folders/yb/v29g2l750ms2bky383fkb6j00000gn/T/opencode/continue-m4-final-mypy-operator.log` | `5d4b6d285b77932e3d08212c3b4974d0a803f98ec60408ac6ccf6a063fa6c19e` |

## Earlier M3 phase-boundary verification (historical; superseded by M4)

The M3 candidate was source-frozen at these exact SHA-256 values:

| File | SHA-256 |
| --- | --- |
| Continuation operator | `c7068b1edb935e5497de1fbaaa303e13f21e743d0a779ecfec899f5a2981f684` |
| Continuation tests | `d105aa96ca3c871d3d4bfcb5efec3914189ab3eef357917526fd1979d8cfbc6d` |
| Continuation packet | `6e627185ff56d8ab156237b8b69ddc1c1440cb0656ef00a6c1f4ff748a44dc9d` |
| Frozen original G1 operator / tests | `701cca098ce005703cc97d298adde7c7072e61ce8bf233b0f941c815ffa7e922` / `04b79e5fea57bb527dbf4015d401aff59697069dfa3c7fc2aee66851585e2a8b` |
| Frozen recovery operator / tests | `e3c47d6c7b7634c5578032df06795d4363205804f475d58d80f4560e7c8b6f45` / `762df8cb9e932ada219c1afe6b7b709c9e2dc4438cde732bcf6a5b041ef1f887` |

| Check | Earlier actual result |
| --- | --- |
| Focused continuation tests | **63 passed**, 15 dependency deprecation warnings, 1.62 s |
| Focused operator coverage | **99.63%** — 268 statements, 1 missed |
| Full repository pytest | **3,081 passed, 21 skipped**, 8,969 warnings, 58.77 s |
| Full `src/foundry_router` coverage | **90.46%** — 11,472 statements, 1,095 missed |
| Ruff lint | Passed for `src`, continuation operator and focused tests: “All checks passed!” |
| Ruff format | Passed for the same paths: “78 files already formatted.” |
| Mypy source | `.venv/bin/mypy src` passed: no issues in 76 source files |
| Mypy continuation operator | `MYPYPATH=src:scripts/quality .venv/bin/mypy scripts/quality/table_production_acceptance_continue.py` passed: no issues in one file |
| SonarQube | N/A — `scripts/quality/sonarqube-scan.sh` is absent |

The stopped-prefix proof now accepts public ready-route **403 or 404 only after**
all revisions are explicitly inactive, every revision has zero workers, and the
bound ingress policy is DENY. The proof records status/classification, revision
names, worker count and DENY binding, and is compared again at apply. Tests reject
a stopped `200` and reject using `404` when any revision remains active, even with
zero workers. After promotion, a live `403` remains mandatory before executor
Allow; after the targeted restart a live `403` remains mandatory as well. Tests
injecting `404` at either live boundary fail closed and do not publish G1 results.
All of these are fake-Azure/unit-test assertions: no live Azure worker, ingress,
state, or original slot was changed or consumed. Synthetic marker mutations were
confined to pytest temporary fixtures.

The M1/M2 ProblemDetails, two explicit read-only ingress omissions, reference-kind
and capture-hash coverage recorded below remains in the current candidate and was
included in this focused rerun. Original G1 and recovery helper/test hashes were
rechecked and match; the continuation remains outside `src/foundry_router`.

Focused/full pytest captures are private mode-600 files in the approved temporary
directory; coverage data is outside the repository. Commands run:

```text
COVERAGE_FILE=<approved-temp>/continue-m3-final-focused.coverage \
  .venv/bin/python -m coverage run --source=scripts/quality -m pytest \
  tests/unit/test_table_production_acceptance_continue.py
COVERAGE_FILE=<approved-temp>/continue-m3-final-focused.coverage \
  .venv/bin/python -m coverage report -m \
  --include=scripts/quality/table_production_acceptance_continue.py
COVERAGE_FILE=<approved-temp>/continue-m3-final-full.coverage \
  .venv/bin/python -m pytest --cov=src/foundry_router --cov-report=term-missing
.venv/bin/ruff check src scripts/quality/table_production_acceptance_continue.py \
  tests/unit/test_table_production_acceptance_continue.py
.venv/bin/ruff format --check src scripts/quality/table_production_acceptance_continue.py \
  tests/unit/test_table_production_acceptance_continue.py
.venv/bin/mypy src
MYPYPATH=src:scripts/quality .venv/bin/mypy \
  scripts/quality/table_production_acceptance_continue.py
```

M3 private capture SHA-256 values:

| Capture | SHA-256 |
| --- | --- |
| `/private/var/folders/yb/v29g2l750ms2bky383fkb6j00000gn/T/opencode/continue-m3-final-focused.log` | `9ffe99e0c91613c31ef2a3dbbc66cc3898d7471dbccaa6555bb692d2f2a98a74` |
| `/private/var/folders/yb/v29g2l750ms2bky383fkb6j00000gn/T/opencode/continue-m3-final-full.log` | `9144672eb8f05988f8cbd030fa7ae5020ae9e8b856cba9f91bfce7242dc75673` |
| `/private/var/folders/yb/v29g2l750ms2bky383fkb6j00000gn/T/opencode/continue-m3-final-ruff-check.log` | `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18` |
| `/private/var/folders/yb/v29g2l750ms2bky383fkb6j00000gn/T/opencode/continue-m3-final-ruff-format.log` | `1a3c6aa46d7f5260e23740995cfa3cf8617f1bd5d18465e940eb76f39be45866` |
| `/private/var/folders/yb/v29g2l750ms2bky383fkb6j00000gn/T/opencode/continue-m3-final-mypy-src.log` | `b1d14a638cdcd6b7a7d5368e3cc2ca927b3e1f1b4e26cbe9b1844d7698aabdf2` |
| `/private/var/folders/yb/v29g2l750ms2bky383fkb6j00000gn/T/opencode/continue-m3-final-mypy-operator.log` | `5d4b6d285b77932e3d08212c3b4974d0a803f98ec60408ac6ccf6a063fa6c19e` |

## Earlier M1/M2 compatibility verification (historical; superseded by M3)

That M1/M2 candidate was source-frozen at these SHA-256 values:

| File | SHA-256 |
| --- | --- |
| Continuation operator | `8d82c443cdff7f8ab8bd1f24f2bc782c887b210b7dc2155fce94c7c1436d6fa7` |
| Continuation tests | `0c5c07f4567f9bf4f1ab2da092a41263dd5e1c34f6986818a80d3030990bd79b` |
| Continuation packet | `73cc97532614ad0687b60dbf32531c72401902b582edf042bbe16a4d8d60c87e` |
| Frozen original G1 operator / tests | `701cca098ce005703cc97d298adde7c7072e61ce8bf233b0f941c815ffa7e922` / `04b79e5fea57bb527dbf4015d401aff59697069dfa3c7fc2aee66851585e2a8b` |
| Frozen recovery operator / tests | `e3c47d6c7b7634c5578032df06795d4363205804f475d58d80f4560e7c8b6f45` / `762df8cb9e932ada219c1afe6b7b709c9e2dc4438cde732bcf6a5b041ef1f887` |

| Check | Earlier actual result |
| --- | --- |
| Focused continuation tests | **57 passed**, 15 dependency deprecation warnings, 1.61 s |
| Focused operator coverage | **99.61%** — 256 statements, 1 missed |
| Full repository pytest | **3,075 passed, 21 skipped**, 8,969 warnings, 58.40 s |
| Full `src/foundry_router` coverage | **90.46%** — 11,472 statements, 1,095 missed |
| Ruff lint | Passed for `src`, continuation operator and focused tests: “All checks passed!” |
| Ruff format | Passed for the same paths: “78 files already formatted.” |
| Mypy source | `.venv/bin/mypy src` passed: no issues in 76 source files |
| Mypy continuation operator | `MYPYPATH=src:scripts/quality .venv/bin/mypy scripts/quality/table_production_acceptance_continue.py` passed: no issues in one file |
| SonarQube | N/A — `scripts/quality/sonarqube-scan.sh` is absent |

The corrected fixtures now represent the reported no-code ProblemDetails rejection:
`error_code` remains `null`, the observed title and validation errors are bound,
and the local classification is explicitly distinguished from an Azure error code.
The success test also exercises a validation envelope omitting exactly the two
read-only ingress keys `fqdn` and `targetPortHttpScheme`; the live synthetic GET
retains both, the copied comparison removes only those keys, and preparation leaves
the GET fixture unchanged. Tests refuse invented provider details, other
configuration drift, incorrect reference kinds, and mismatched validation/what-if
capture hashes. Validation `id` is bound as `response_id`; the what-if request URI
is bound as `request_target`, with each read-only response capture hash checked.
These are synthetic fixtures/tests, not independent inspection of actual Azure
captures.

The focused and full logs are private, mode-600 captures in the approved temporary
directory. Coverage data is also outside the repository. The exact commands were:

```text
COVERAGE_FILE=<approved-temp>/continue-evidence-final-focused.coverage \
  .venv/bin/python -m coverage run --source=scripts/quality -m pytest \
  tests/unit/test_table_production_acceptance_continue.py
COVERAGE_FILE=<approved-temp>/continue-evidence-final-focused.coverage \
  .venv/bin/python -m coverage report -m \
  --include=scripts/quality/table_production_acceptance_continue.py
COVERAGE_FILE=<approved-temp>/continue-evidence-final-full.coverage \
  .venv/bin/python -m pytest --cov=src/foundry_router --cov-report=term-missing
.venv/bin/ruff check src scripts/quality/table_production_acceptance_continue.py \
  tests/unit/test_table_production_acceptance_continue.py
.venv/bin/ruff format --check src scripts/quality/table_production_acceptance_continue.py \
  tests/unit/test_table_production_acceptance_continue.py
.venv/bin/mypy src
MYPYPATH=src:scripts/quality .venv/bin/mypy \
  scripts/quality/table_production_acceptance_continue.py
```

M1/M2 capture SHA-256 values:

| Private capture | SHA-256 |
| --- | --- |
| `/private/var/folders/yb/v29g2l750ms2bky383fkb6j00000gn/T/opencode/continue-evidence-final-focused.log` | `49f22efa55d6d1f656d95c2bcde4360a1429c6762f17e11a68ef5e3d1bae9d20` |
| `/private/var/folders/yb/v29g2l750ms2bky383fkb6j00000gn/T/opencode/continue-evidence-final-full.log` | `cd957e87e76d11e9899f1bffe6726d95b27e69c0514831f3e3d047c4c50455ea` |
| `/private/var/folders/yb/v29g2l750ms2bky383fkb6j00000gn/T/opencode/continue-evidence-final-ruff-check.log` | `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18` |
| `/private/var/folders/yb/v29g2l750ms2bky383fkb6j00000gn/T/opencode/continue-evidence-final-ruff-format.log` | `1a3c6aa46d7f5260e23740995cfa3cf8617f1bd5d18465e940eb76f39be45866` |
| `/private/var/folders/yb/v29g2l750ms2bky383fkb6j00000gn/T/opencode/continue-evidence-final-mypy-src.log` | `b1d14a638cdcd6b7a7d5368e3cc2ca927b3e1f1b4e26cbe9b1844d7698aabdf2` |
| `/private/var/folders/yb/v29g2l750ms2bky383fkb6j00000gn/T/opencode/continue-evidence-final-mypy-operator.log` | `5d4b6d285b77932e3d08212c3b4974d0a803f98ec60408ac6ccf6a063fa6c19e` |

The operator mypy command includes `scripts/quality` because the operator imports
its sibling harness modules by top-level module name. The earlier `MYPYPATH=src`
only attempt lacked that search path and failed module resolution; this was an
incomplete invocation, not a source/type defect. The correctly configured command
above passes.

## Earlier pre-M1/M2 verification (historical; superseded)

### Earlier candidate and frozen dependency hashes

The continuation candidate matched the requested frozen fingerprints before and
after local checks. The previously frozen G1 and recovery dependencies also match
their approved hashes:

| File | SHA-256 | Result |
| --- | --- | --- |
| Continuation operator | `b4417b262beefa80a85a7d2d4f5d596cbeb466e342e2794274c67ef8ddb3f973` | Frozen candidate unchanged |
| Continuation tests | `983acd371e9301d36efa11836d50f4dbc3db022684fe999d553a07fb9cea8345` | Frozen candidate unchanged |
| Continuation packet | `4f54b86323f14b6920c9e1b53eaca66b4fd5d4fd6854ed6a7195ea2a00963f0b` | Frozen packet unchanged |
| Original G1 operator | `701cca098ce005703cc97d298adde7c7072e61ce8bf233b0f941c815ffa7e922` | Matches frozen dependency |
| Original G1 tests | `04b79e5fea57bb527dbf4015d401aff59697069dfa3c7fc2aee66851585e2a8b` | Matches frozen dependency |
| Recovery operator | `e3c47d6c7b7634c5578032df06795d4363205804f475d58d80f4560e7c8b6f45` | Matches frozen dependency |
| Recovery tests | `762df8cb9e932ada219c1afe6b7b709c9e2dc4438cde732bcf6a5b041ef1f887` | Matches frozen dependency |

### Earlier results

| Check | Actual result |
| --- | --- |
| Focused continuation tests | **42 passed**, 15 dependency deprecation warnings, 1.25 s |
| Focused operator coverage | **99.58%** — 240 statements, 1 missed |
| Full repository pytest | **3,060 passed, 21 skipped**, 8,969 warnings, 58.33 s |
| Full `src/foundry_router` coverage | **90.46%** — 11,472 statements, 1,095 missed |
| Ruff lint | Passed for `src`, the continuation operator, and focused tests: “All checks passed!” |
| Ruff format | Passed for the same paths: “78 files already formatted.” |
| Mypy source | `.venv/bin/mypy src` passed: no issues in 76 source files |
| Mypy continuation operator (earlier incomplete path) | `MYPYPATH=src` omitted `scripts/quality` and failed sibling-module resolution. This was an invocation-path issue, not a source/type defect; the correctly configured command passed in the final run above. |
| Supplemental mypy path diagnostic | `MYPYPATH=src:scripts/quality` passed: no issues in one operator file. |
| SonarQube | N/A — `scripts/quality/sonarqube-scan.sh` is absent |

The tests exercise the corrected API version and template-only request, rejection
and validation/what-if evidence binding, refusal of ambiguous or mismatched evidence,
inactive-worker and configuration guards, financial checks before the first paid
marker, and bounded worker/public propagation behavior. The successful synthetic
chain consumes only the four original slots and their existing USD 0.01792
reservation, checks original/recovery history immutability, refuses replay, and
asserts the expected one-PATCH/allow/four-case/deny/restart mutation sequence with
no production fake mutations. Failure cases assert that uncertain PATCH/payment,
missing counters, or finance drift do not retry or advance later slots. These are
mocked test results, not proof of live state or execution.

### Earlier commands and private captures

Focused and full pytest output is retained privately outside the repository in the
approved temporary directory. Coverage data is also outside the repository:

```text
COVERAGE_FILE=<approved-temp>/continuation-final-focused.coverage \
  .venv/bin/python -m coverage run --source=scripts/quality -m pytest \
  tests/unit/test_table_production_acceptance_continue.py
COVERAGE_FILE=<approved-temp>/continuation-final-focused.coverage \
  .venv/bin/python -m coverage report -m \
  --include=scripts/quality/table_production_acceptance_continue.py

COVERAGE_FILE=<approved-temp>/continuation-final-full.coverage \
  .venv/bin/python -m pytest --cov=src/foundry_router --cov-report=term-missing

.venv/bin/ruff check src scripts/quality/table_production_acceptance_continue.py \
  tests/unit/test_table_production_acceptance_continue.py
.venv/bin/ruff format --check src scripts/quality/table_production_acceptance_continue.py \
  tests/unit/test_table_production_acceptance_continue.py
.venv/bin/mypy src
MYPYPATH=src .venv/bin/mypy scripts/quality/table_production_acceptance_continue.py
```

Actual private capture paths and SHA-256 fingerprints:

| Capture | SHA-256 |
| --- | --- |
| `/private/var/folders/yb/v29g2l750ms2bky383fkb6j00000gn/T/opencode/continuation-final-focused.log` | `09fd8bee7545106ad30e676a22e44270ab12be475f775570bb1326ff66d3bcdd` |
| `/private/var/folders/yb/v29g2l750ms2bky383fkb6j00000gn/T/opencode/continuation-final-full.log` | `64fa598b8a5dc3471bfd54d92d56c200d83a62ab5d3c9b84c333813da8daeb78` |
| `/private/var/folders/yb/v29g2l750ms2bky383fkb6j00000gn/T/opencode/continuation-final-ruff-check.log` | `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18` |
| `/private/var/folders/yb/v29g2l750ms2bky383fkb6j00000gn/T/opencode/continuation-final-ruff-format.log` | `1a3c6aa46d7f5260e23740995cfa3cf8617f1bd5d18465e940eb76f39be45866` |
| `/private/var/folders/yb/v29g2l750ms2bky383fkb6j00000gn/T/opencode/continuation-final-mypy-src.log` | `b1d14a638cdcd6b7a7d5368e3cc2ca927b3e1f1b4e26cbe9b1844d7698aabdf2` |
| `/private/var/folders/yb/v29g2l750ms2bky383fkb6j00000gn/T/opencode/continuation-final-mypy-operator.log` | `946c05a0f129de051cbd0f1eb1782eecdcff166bdb78e135f737477ed51423af` |
| `/private/var/folders/yb/v29g2l750ms2bky383fkb6j00000gn/T/opencode/continuation-final-mypy-operator-path-diagnostic.log` | `5d4b6d285b77932e3d08212c3b4974d0a803f98ec60408ac6ccf6a063fa6c19e` |

The earlier `MYPYPATH=src`-only invocation failed to resolve the operator's sibling
script modules. A diagnostic with `MYPYPATH=src:scripts/quality` passed even then;
the import-path omission was not evidence of a source/type defect. The final run
above reran the complete local checks against the corrected M1/M2 candidate with
the properly configured operator mypy command.

## Scope and outstanding gates

The current M4 mocked verification and full source suite pass their coverage gates.
No Azure/ARM/CLI calls, actual prepare/apply, worker inspection, paid provider call,
staging, operator/runtime source edit, Docker build, Azurite rerun, or commit was
performed; only this verification document was updated. A separate exact-prepared
checker and exact-packet review were reported as concurrent read-only checks; the
fresh-prepare report included a full three-inactive-revision inventory and no active
jobs. This verifier did not inspect or change their private metadata/artifacts, and
those live-state reports are not independently verified here. The reported
stopped/no-worker state, absence of paid markers and archived private partial
artifacts likewise remain external reports. The three out-of-scope production/P2
drafts and their body-hash-preserved archive were not accessed, moved, or altered by
this verifier; that preservation remains a coordinator/user report. No such drafts
were added by this verifier. Pre-existing dirty user work was preserved. Prior
evidence for the immutable image and matching 76 runtime Python file hashes is
reused only as historical baseline; Docker/image and Azurite checks were not
repeated. Frozen G1/recovery helper/test hashes were rechecked and match. The
continuation operator remains outside `src/foundry_router`.

Independent contextual/exact review, actual read-only preparation, separate
execution approval, and any live continuation remain separate gates. Production
remains memory-backed with one replica; this record does not establish deployment,
Azure behavior, or production cut-over.
