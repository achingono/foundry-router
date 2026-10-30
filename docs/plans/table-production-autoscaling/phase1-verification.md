# Phase 1 Harness Verification

**Status: Partially implemented — local harness verification only; not execution approval.**
Recorded 2026-10-30. This verification covers the [Phase 1 acceptance packet](phase1-packet.md),
[`table_production_acceptance.py`](../../../scripts/quality/table_production_acceptance.py), and
its [unit tests](../../../tests/unit/test_table_production_acceptance.py). It does not approve or
execute an Azure change.

## Final EP-M2 direct-template-patch verification — 2026-10-30

Current SHA-256 fingerprints, confirmed unchanged after checks:

| File | SHA-256 |
| --- | --- |
| `scripts/quality/table_production_acceptance.py` | `701cca098ce005703cc97d298adde7c7072e61ce8bf233b0f941c815ffa7e922` |
| `tests/unit/test_table_production_acceptance.py` | `04b79e5fea57bb527dbf4015d401aff59697069dfa3c7fc2aee66851585e2a8b` |
| `docs/plans/table-production-autoscaling/phase1-packet.md` | `59d486b5a459260f2a6f0e82e5a0f2cb084f97f47096481a677915ecfc1f4d5c` |

| Check | Actual final result |
| --- | --- |
| Focused harness tests | **95 passed**, 15 warnings, 0.55 seconds. |
| Focused harness coverage | **97.10%** (587 statements, 17 missed). |
| Full repository suite | **2,982 passed, 21 skipped**, **90.46% source coverage** (11,472 statements, 1,095 missed), 57.91 seconds; 8,969 warnings. |
| Ruff lint | Passed for `src`, the acceptance script, and its tests: “All checks passed!” |
| Ruff formatting | Passed for the same paths: “78 files already formatted.” |
| Mypy source | Passed: no issues in 76 source files. |
| Mypy harness | `MYPYPATH=src` passed: no issues in one source file. |
| EP-M2 PATCH and secret-ref guards | `test_template_patch_preserves_refs_resources_and_input_without_cli_normalization`, all six `test_template_proposal_rejects_unreviewed_changes` cases, and `test_malformed_proposal_refused_before_consumption_or_azure_mutation` passed. The tests verify template-only PATCH shape, exact `secretRef` preservation without a `value` field, and refusal of drift. |
| EP-M1 writer/ready guards | All-inactive/draining writer-absence polling, unexpected-active/deadline refusal, and inactive-revision-worker readiness guards passed in the same focused run. |

Focused and full pytest logs are retained outside the repository at
`/private/var/folders/yb/v29g2l750ms2bky383fkb6j00000gn/T/opencode/phase1-epm2-final-focused.log`
and
`/private/var/folders/yb/v29g2l750ms2bky383fkb6j00000gn/T/opencode/phase1-epm2-final-full.log`.
Ruff and mypy outputs are in the same directory as `phase1-epm2-final-ruff-check.log`,
`phase1-epm2-final-ruff-format.log`, `phase1-epm2-final-mypy-src.log`, and
`phase1-epm2-final-mypy-harness.log`.

Focused coverage ran before full source coverage, with separate data files:

```text
COVERAGE_FILE=<approved-temp>/phase1-epm2-final-focused.coverage \
  .venv/bin/python -m coverage run --source=scripts/quality -m pytest \
  tests/unit/test_table_production_acceptance.py
COVERAGE_FILE=<approved-temp>/phase1-epm2-final-focused.coverage \
  .venv/bin/python -m coverage report -m \
  --include=scripts/quality/table_production_acceptance.py

COVERAGE_FILE=<approved-temp>/phase1-epm2-final-full.coverage \
  .venv/bin/python -m pytest --cov=src/foundry_router --cov-report=term-missing

.venv/bin/ruff check src scripts/quality/table_production_acceptance.py \
  tests/unit/test_table_production_acceptance.py
.venv/bin/ruff format --check src scripts/quality/table_production_acceptance.py \
  tests/unit/test_table_production_acceptance.py
.venv/bin/mypy src
MYPYPATH=src .venv/bin/mypy scripts/quality/table_production_acceptance.py
```

No Azure calls or mutations, provider HTTP, source edits, Docker build, staging, or commit were
performed by this verifier. Exact review and preparation are separate parallel read-only activities.
The coordinator-reported 15-test Azurite result and matching hashes for the immutable image's 76
runtime files remain external baseline evidence; the EP-M2 change is limited to the external
harness/tests/packet, so no Docker rebuild or dedicated Azurite rerun was needed.

## Previous EP-M1-only verification — 2026-10-30

Current SHA-256 fingerprints, confirmed unchanged after verification:

| File | SHA-256 |
| --- | --- |
| `scripts/quality/table_production_acceptance.py` | `c56e8ce97cde14a48011dc24384c5cab0500851216012a3b1c96d8cf446cb20d` |
| `tests/unit/test_table_production_acceptance.py` | `2565ab3684e97adc612c97a96d909db5cfd4befa89b7529ce16ba251102d7116` |
| `docs/plans/table-production-autoscaling/phase1-packet.md` | `be271e4aa59ddf548b16139b0257c8eb403cc2ac3f89edbe937ed0648cd996f0` |

| Check | Actual final result |
| --- | --- |
| Focused harness tests | **87 passed**, 15 warnings, 0.58 seconds. |
| Focused harness coverage | **96.95%** (557 statements, 17 missed). |
| Full repository suite | **2,974 passed, 21 skipped**, **90.46% source coverage** (11,472 statements, 1,095 missed), 58.30 seconds; 8,969 warnings. |
| Ruff lint | Passed for `src`, the acceptance script, and its tests: “All checks passed!” |
| Ruff formatting | Passed for the same paths: “78 files already formatted.” |
| Mypy source | Passed: no issues in 76 source files. |
| Mypy harness | `MYPYPATH=src` passed: no issues in one source file. |
| EP-M1 writer/ready guards | `test_absence_observes_all_inactive_draining_replicas_before_progress`, both `test_absence_deadline_or_unexpected_active_never_promotes` cases, `test_inactive_workers_still_refused_for_readiness_and_replacement`, and `test_prepare_cold_empty_workers_then_ready` passed; no promotion precedes proved absence. |
| Snapshot command encoding | zlib level 9/base64 round-trip passed; generated command length was **1,135 characters**. |

Focused and full pytest logs are retained outside the repository at
`/private/var/folders/yb/v29g2l750ms2bky383fkb6j00000gn/T/opencode/phase1-epm1-final-focused.log`
and
`/private/var/folders/yb/v29g2l750ms2bky383fkb6j00000gn/T/opencode/phase1-epm1-final-full.log`.
Ruff and mypy outputs are in the same directory as `phase1-epm1-final-ruff-check.log`,
`phase1-epm1-final-ruff-format.log`, `phase1-epm1-final-mypy-src.log`, and
`phase1-epm1-final-mypy-harness.log`.

Focused coverage ran before full source coverage, with separate data files:

```text
COVERAGE_FILE=<approved-temp>/phase1-epm1-final-focused.coverage \
  .venv/bin/python -m coverage run --source=scripts/quality -m pytest \
  tests/unit/test_table_production_acceptance.py
COVERAGE_FILE=<approved-temp>/phase1-epm1-final-focused.coverage \
  .venv/bin/python -m coverage report -m \
  --include=scripts/quality/table_production_acceptance.py

COVERAGE_FILE=<approved-temp>/phase1-epm1-final-full.coverage \
  .venv/bin/python -m pytest --cov=src/foundry_router --cov-report=term-missing

.venv/bin/ruff check src scripts/quality/table_production_acceptance.py \
  tests/unit/test_table_production_acceptance.py
.venv/bin/ruff format --check src scripts/quality/table_production_acceptance.py \
  tests/unit/test_table_production_acceptance.py
.venv/bin/mypy src
MYPYPATH=src .venv/bin/mypy scripts/quality/table_production_acceptance.py
```

No Azure calls/mutations, provider HTTP, source edits, Docker build, staging, or commit were
performed by this verifier. Exact review and read-only prepare are separate parallel activities,
outside these local checks. The coordinator-reported 15-test Azurite result and identical hashes
for all 76 runtime files in the immutable image remain external baseline evidence; no runtime source
was edited by this verifier, so no Docker rebuild or dedicated Azurite rerun was needed.

## Prior source-frozen verification — compressed exec

SHA-256 fingerprints recorded at that verification:

| File | SHA-256 |
| --- | --- |
| `scripts/quality/table_production_acceptance.py` | `35e082c537bc144a59f3ad321175deec31ef0770360ccc856e1f44bc04c97e30` |
| `tests/unit/test_table_production_acceptance.py` | `affa20a3e2d0dbfbfb5dd7fc2cf9d0bef714f7c88bd5d680877ffbd29af3d50a` |
| `docs/plans/table-production-autoscaling/phase1-packet.md` | `8143d2da28a55943e839cb2207c428db2ed073a39ed09af25d51bf69433c02bf` |

All three hashes were confirmed unchanged by a post-check rehash.

| Check | Final result |
| --- | --- |
| Focused harness | **83 passed**, 15 warnings, 0.53 seconds. |
| Focused harness coverage | **96.93%** (554 statements, 17 missed). |
| Full repository suite | **2,970 passed, 21 skipped**, **90.46% source coverage** (11,472 statements, 1,095 missed), 57.12 seconds; 8,969 warnings. |
| Ruff lint | Passed for `src`, the acceptance script, and its tests: “All checks passed!” |
| Ruff format | Passed for the same paths: “78 files already formatted.” |
| Mypy source | Passed: no issues in 76 source files. |
| Mypy harness | `MYPYPATH=src` check passed: no issues in one source file. |
| Compressed snapshot command | zlib level 9 + base64 round-tripped the snapshot program; generated command length **1,135 characters**. The focused targeted-PTY test also passed. |

Full output is retained outside the repository at
`/private/var/folders/yb/v29g2l750ms2bky383fkb6j00000gn/T/opencode/phase1-final-full.log`;
focused output is at
`/private/var/folders/yb/v29g2l750ms2bky383fkb6j00000gn/T/opencode/phase1-final-focused.log`.
The same approved temporary directory contains `phase1-final-ruff-check.log`,
`phase1-final-ruff-format.log`, `phase1-final-mypy-src.log`, and
`phase1-final-mypy-harness.log`.

Focused coverage ran before full source coverage, with separate files:

```text
COVERAGE_FILE=<approved-temp>/phase1-final-focused.coverage \
  .venv/bin/python -m coverage run --source=scripts/quality -m pytest \
  tests/unit/test_table_production_acceptance.py
COVERAGE_FILE=<approved-temp>/phase1-final-focused.coverage \
  .venv/bin/python -m coverage report -m \
  --include=scripts/quality/table_production_acceptance.py

COVERAGE_FILE=<approved-temp>/phase1-final-full.coverage \
  .venv/bin/python -m pytest --cov=src/foundry_router --cov-report=term-missing

.venv/bin/ruff check src scripts/quality/table_production_acceptance.py \
  tests/unit/test_table_production_acceptance.py
.venv/bin/ruff format --check src scripts/quality/table_production_acceptance.py \
  tests/unit/test_table_production_acceptance.py
.venv/bin/mypy src
MYPYPATH=src .venv/bin/mypy scripts/quality/table_production_acceptance.py
```

Coordinator-reported fresh read-only prepare succeeded; coordinator reports no Azure mutation or
provider inference. It was separate from this local verification. No Azure command, provider HTTP,
source edit, staging, Docker build, or commit was performed by this verifier. The coordinator's
existing 15-test Azurite result and exact 76-runtime-file immutable-image hash/import evidence remain
external baseline evidence; no runtime source was edited by this verifier and those checks were not
repeated.

## Previous corrected-harness verification — 2026-10-30

These prior results are retained; they are superseded by the final source-frozen run above.

Current SHA-256 fingerprints at verification time:

| File | SHA-256 |
| --- | --- |
| `scripts/quality/table_production_acceptance.py` | `b0a30682941ed46e368fbd59b0148bb80c9634a91272da363bc17e122d4089b2` |
| `tests/unit/test_table_production_acceptance.py` | `3ec4dbff84f0cfd41c4b6bf871cec813f3b881310c936bd0bf20c44f816f011b` |

Both hashes were confirmed unchanged by a post-check rehash.

| Check | Result at that verification |
| --- | --- |
| Focused corrected-harness tests | **83 passed**, 15 deprecation warnings, 0.55 seconds. |
| Focused harness coverage | **96.93%** (553 statements, 17 missed), above the 80% target. |
| Full repository tests | **2,970 passed, 21 skipped**, **90.46% source coverage** (11,472 statements, 1,095 missed), 57.43 seconds; 8,969 warnings. |
| Ruff lint | Passed on `src`, the acceptance script, and its unit tests: “All checks passed!” |
| Ruff formatting | Passed on the same paths: “78 files already formatted.” |
| Mypy source | `.venv/bin/mypy src` passed: no issues in 76 source files. |
| Mypy harness | `MYPYPATH=src .venv/bin/mypy scripts/quality/table_production_acceptance.py` passed: no issues in one source file. |

The focused and full test outputs are retained outside the repository in the approved temporary
directory as `phase1verify-corrected-focused.log` and `phase1verify-corrected-full.log`. Ruff and
mypy outputs are in `phase1verify-corrected-ruff.log`, `phase1verify-corrected-format.log`,
`phase1verify-corrected-mypy-src.log`, and `phase1verify-corrected-mypy-harness.log`.

Commands run, sequentially for focused coverage followed by full source coverage:

```text
COVERAGE_FILE=<approved-temp>/phase1verify-corrected-focused.coverage \
  .venv/bin/python -m coverage run --source=scripts/quality -m pytest \
  tests/unit/test_table_production_acceptance.py
COVERAGE_FILE=<approved-temp>/phase1verify-corrected-focused.coverage \
  .venv/bin/python -m coverage report -m \
  --include=scripts/quality/table_production_acceptance.py

COVERAGE_FILE=<approved-temp>/phase1verify-corrected-full.coverage \
  .venv/bin/python -m pytest --cov=src/foundry_router --cov-report=term-missing

.venv/bin/ruff check src scripts/quality/table_production_acceptance.py \
  tests/unit/test_table_production_acceptance.py
.venv/bin/ruff format --check src scripts/quality/table_production_acceptance.py \
  tests/unit/test_table_production_acceptance.py
.venv/bin/mypy src
MYPYPATH=src .venv/bin/mypy scripts/quality/table_production_acceptance.py
```

The actual approved temporary directory was `/private/var/folders/yb/v29g2l750ms2bky383fkb6j00000gn/T/opencode`.
The runs used `.venv` on macOS with Python 3.14.10 and pytest 8.4.2. This increment verified the
external acceptance harness only: no source edits, Azure mutations/CLI operation, provider HTTP,
staging, Docker build, or commit were performed.

## Historical verification — initial 56-test harness

The following first-pass results are retained as history; they are superseded for the corrected
harness by the fresh results above, not erased or reinterpreted.

### Historical results

| Check | Actual result |
| --- | --- |
| Focused harness tests | **56 passed**, 15 deprecation warnings, 0.25 seconds. The tests use fake Azure state and `httpx.MockTransport`; no Azure or paid provider call was made. |
| Focused harness coverage | **95.19%** (541 statements, 26 missed), above the 80% target. The first pytest-cov module selector did not collect this dynamically loaded script; rerunning coverage with `coverage run --source=scripts/quality` collected the script correctly. The initial no-data warning was a coverage-selector issue, not a test failure. |
| Full test suite | **2,943 passed, 21 skipped**, source coverage **90.46%** (11,472 statements, 1,095 missed), 57.22 seconds. This exceeds the 80% target. The run reported 8,969 warnings, predominantly dependency deprecations; one Pydantic serializer warning was also reported. |
| Ruff check | Passed for `src`, the acceptance script, and its unit test: “All checks passed!” |
| Ruff format check | Passed for the same paths: “78 files already formatted.” |
| Mypy source check | `.venv/bin/mypy src` passed: no issues in 76 source files. |
| Mypy explicit harness check | `MYPYPATH=src .venv/bin/mypy scripts/quality/table_production_acceptance.py` passed: no issues in one source file. Invoking mypy on the script without `MYPYPATH=src` resolved an installed, untyped `foundry_router` package and reported three import/subclass errors; selecting the local source tree resolved that environment mismatch without code changes. |
| SonarQube | **N/A** — `scripts/quality/sonarqube-scan.sh` is absent from the repository. |
| Documentation links | Six local relative links across the Phase 1 packet, this verification file, and migration mechanics resolve. |

The focused test output and coverage report were retained outside the repository in the approved
temporary directory as `phase1verify-focused.log` and `phase1verify-focused-coverage.log`. The full
pytest output is `phase1verify-full.log` in that same directory. These are private local captures,
not committed artifacts.

### Historical commands run

```text
COVERAGE_FILE=<approved-temp>/phase1verify-focused-file.coverage \
  .venv/bin/python -m coverage run --source=scripts/quality -m pytest \
  tests/unit/test_table_production_acceptance.py
COVERAGE_FILE=<approved-temp>/phase1verify-focused-file.coverage \
  .venv/bin/python -m coverage report -m \
  --include=scripts/quality/table_production_acceptance.py

COVERAGE_FILE=<approved-temp>/phase1verify-full.coverage \
  .venv/bin/python -m pytest --cov=src/foundry_router --cov-report=term-missing

.venv/bin/ruff check src scripts/quality/table_production_acceptance.py \
  tests/unit/test_table_production_acceptance.py
.venv/bin/ruff format --check src scripts/quality/table_production_acceptance.py \
  tests/unit/test_table_production_acceptance.py
.venv/bin/mypy src
MYPYPATH=src .venv/bin/mypy scripts/quality/table_production_acceptance.py
```

The actual approved temporary directory was `/private/var/folders/yb/v29g2l750ms2bky383fkb6j00000gn/T/opencode`.
The runs used the repository `.venv` on macOS with Python 3.14.10 and pytest 8.4.2.

## Link-check detail

- Six local relative links across `phase1-packet.md`, `phase1-verification.md`, and
  `table-migration-mechanics.md` resolve. The packet's Microsoft Learn URL is external and was not
  part of the local relative-link check.

## Scope limits and outstanding gates

- This verifier ran no harness `prepare` or `apply`, Azure CLI operation, paid HTTP request, staging,
  Docker build, deployment, restart, resource mutation, or commit. An earlier coordinator report
  records successful read-only preparation without mutation or provider inference; the current exact
  review and read-only preparation are separate parallel activities, outside this local verification.
  Mocked orchestration tests are local evidence only.
- The coordinator's earlier baseline evidence reports the exact immutable image pull, network-
  disabled imports, and matching hashes for all 76 runtime Python files. It also reports 15 passing
  dedicated Azurite tests. Those remain external baseline evidence and were not repeated here: this
  increment is the external acceptance harness, the task emulator was stopped, and no runtime source
  was edited by this verifier. See the [plan evidence](evidence.md); those coordinator results are
  not independent reruns in this record.
- Independent exact-packet/deep review, fenced Azure execution, four paid Responses cases, targeted
  restart, and a separately reviewed restoration packet remain open.
  Successful local tests do not establish Azure behavior or execution readiness.
- Production remains memory-backed with `maxReplicas: 1`. The result is not a production cut-over
  approval and must not be represented as deployed acceptance.
