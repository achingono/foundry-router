# G1 fence recovery independent verification

Date: 2026-10-30. Scope: local verification of the recovery runner and tests only.
This report does not authorize or claim Azure recovery.

## Verdict

**Local verification passed.** The focused suite passed 36 tests with 98% recovery-runner
statement coverage; the full suite passed 3,018 tests, skipped 21, and measured 90.46%
`src/foundry_router` coverage. Repository Ruff lint/format and mypy passed. No code or
configuration was changed by this verifier; only this report was added.

The reviewed implementation is [ready for read-only preparation](implementation-review.md),
not execution. Actual private preparation, live binding/disjointness checks, a separately
reviewed exact recovery approval, and any recovery execution remain unperformed and required.
Successful local mocks do not establish Azure propagation, worker absence, paid settlement,
or restart persistence.

## Exact inputs

| File | SHA-256 | Result |
| --- | --- | --- |
| [Recovery runner](../../../../scripts/quality/table_production_acceptance_recovery.py) | `e3c47d6c7b7634c5578032df06795d4363205804f475d58d80f4560e7c8b6f45` | Matches reviewed binding |
| [Recovery tests](../../../../tests/unit/test_table_production_acceptance_recovery.py) | `762df8cb9e932ada219c1afe6b7b709c9e2dc4438cde732bcf6a5b041ef1f887` | Matches reviewed binding |
| [Operational packet](packet.md) | `3597d7244f46eedc4e6750d76b2855986acfd006900b0b19e9ceddc56037d532` | Matches reviewed binding |
| Frozen G1 helper | `701cca098ce005703cc97d298adde7c7072e61ce8bf233b0f941c815ffa7e922` | Unchanged |
| Frozen G1 tests | `04b79e5fea57bb527dbf4015d401aff59697069dfa3c7fc2aee66851585e2a8b` | Unchanged |

The coordinator's paused production-migration files were outside the repository during these
checks. Their observed temporary-file hashes were `cae9df411bdc6a254a860cd760e4bf2b03defc40ddf74f72103295e9ec13565c`
(Python) and `dacb2e987cf60d818b0adbe035434bd516b4947f364405da91a8283280a7a958`
(Markdown). They were not included in current-repository test, lint, format, or type-check
inputs. The coordinator supplied the byte-identical move/pause proof.

## Executed checks

| Check | Observed result | Private capture |
| --- | --- | --- |
| Focused recovery suite and exact-file coverage | `36 passed`, 15 dependency deprecation warnings; 387 statements, 8 missed, **98%** statement coverage; ≥80% gate passed | `/private/var/folders/yb/v29g2l750ms2bky383fkb6j00000gn/T/opencode/recovery-focused-approved-temp.log` — SHA-256 `3e43e8668f216fb18dac6d7a2250aa4d44afdc3637f961e8ad134f9c989e3930` |
| Full `.venv` pytest with source coverage gate | **3,018 passed, 21 skipped**, 90.46% source coverage; ≥80% gate passed; 8,969 warnings | `/private/var/folders/yb/v29g2l750ms2bky383fkb6j00000gn/T/opencode/recovery-final-full.log` — SHA-256 `3555bc783af01760f1f1ec5d630b28f72d9b868264bb0f07986b926014975976` |
| `.venv/bin/ruff check .` | Passed across the current repository | `/private/var/folders/yb/v29g2l750ms2bky383fkb6j00000gn/T/opencode/recovery-final-ruff-check.log` — SHA-256 `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18` |
| `.venv/bin/ruff format --check .` | Passed; 1,091 files already formatted | `/private/var/folders/yb/v29g2l750ms2bky383fkb6j00000gn/T/opencode/recovery-final-ruff-format.log` — SHA-256 `e2fa09903898345cf359e4faa05cdd9150678954565aee51101358badcae780e` |
| `MYPYPATH=src:scripts/quality .venv/bin/mypy src scripts/quality/table_production_acceptance_recovery.py` | Passed; no issues in 77 source files | `/private/var/folders/yb/v29g2l750ms2bky383fkb6j00000gn/T/opencode/recovery-final-mypy.log` — SHA-256 `6de57c7814104e6de9b6c70898a5f0e106413d679270d2dee07f3e93c936e234` |

The focused test module was loaded with `importlib`; an initial pytest-cov module selector did
not recognize that dynamic import and reported zero coverage. The result above is from a fresh
run using Coverage.py's exact-file include selector, followed by `coverage report --fail-under=80`.
No implementation change was made to obtain coverage.

## Test-case audit

- **Cold rebase:** the complete recovery test passes both warm and cold branches. The cold case
  verifies that its old-image baseline is not treated as current-image restart acceptance.
  `cold_balance` injects financial drift during warm-up and asserts the runner stops before
  deactivation or any paid slot.
- **Unstarted-slot ownership:** preparation refuses representative existing case, drain, stop,
  update, restart, unknown-journal, and prior-recovery markers. Successful warm/cold runs advance
  exactly the four original slots, retain the original ledger allocation, and reject a second
  apply after consumption.
- **Propagation/deadline:** public polling covers delayed 200/503/403 observations and a
  trickling response deadline. Synthetic worker transition and overall-budget tests cover
  no-op replacement, alarm restoration, and bounded CLI cleanup. The successful synthetic path
  also observes draining old replicas to zero before the PATCH precondition. These are local
  simulations, not live timing evidence.
- **Financial chain:** injected between-case balance drift, a missing current counter, cold-start
  balance drift, restart balance drift, invalid usage, and reserve overrun all refuse completion.
  The success path checks ordered debit/account continuity and unchanged original ledger bytes.
- **No replay:** uncertain paid dispatch retains the consumed slot and prevents the next slot;
  the test asserts a second apply is refused after successful consumption. Failure tests assert
  no result completion, refund, or later-slot consumption.

## Reused evidence and outstanding gates

- The [parent evidence](../evidence.md) records the existing deployed-image comparison (76
  runtime Python files matched) and 15 passing Azurite integration tests. This increment adds
  only an operator recovery harness/tests and report; this verifier made no runtime change and
  did **not** rebuild Docker or rerun Azurite. Those results are reused historical evidence, not
  new recovery acceptance.
- `scripts/quality/sonarqube-scan.sh` is absent. Sonar is **N/A**, not a passed scan.
- The independent implementation review reports zero unresolved Critical/Major findings and
  permits read-only preparation only. Exact fresh private artifacts and approval, current
  Azure/resource checks, one-time apply, four real slot settlements, final fence/restart, and
  staged cleanup remain open. Production remains memory-backed with one replica pending its
  separate migration gates.
- Existing dirty source, test, documentation, and plan work from other writers was left intact.
  No live Azure/HTTP preparation, paid call, staging, Docker command, or production mutation was run.
