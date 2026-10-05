# Five independent Major findings — recovery implementation evidence

## Status: Implemented (local verification); production deployment Planned

The operator supplied independent amendment approval from session
`ses_ef6422f4effeLjrO87PAowPxJu`. Approval was recorded in
[the amendment](recovery-amendment.md) before code fixes. No further OpenCode reviewer was launched.
Independent implementation re-review can follow; this document does not claim that it has passed.

## Fixes and fault evidence

| Independent Major | Fix | Reproduction evidence |
| --- | --- | --- |
| Failed settlement becomes free at expiry | Memory retains intended charge before settlement. Table ETag-writes `settlement_charge_usd` before balance settlement. Valid intent wins; otherwise every expired pending/legacy/pre-egress row charges full reserve. Fresh balance and reservation ETags guard the same settlement/reaper batch. | Failed actual settlement then expiry; intent-write failure then full-reserve recovery; restart; intent commit then timeout; reaper intent conflict recomputation; settlement/reaper commit then timeout with no double debit |
| Ambiguous reserve acknowledged as False | Table exceptions/exhausted conflicts raise typed errors. Possible ownership captured before transaction; uncertain IDs reject reuse until confirmed finalization. Routing's existing typed-failure boundary stops all selection/egress. | Unit reserve commit-then-timeout, zero backend calls and no second partition; real SDK/Azurite committed transaction with lost acknowledgement; SDK outage now expects typed error |
| Metering missing from fingerprint, sync/admission race | Metered group set is part of fingerprint. Local sync/admission/assessment/finalize/reaper serialize under the store lock, resolving published aliases while protected. Only completed sync publishes aliases; old/attempted partitions remain discoverable. | Same Settings metering flip while pending, both object/mapping stubs; blocked admission vs membership sync interleaving; failed sync retains aliases and old partitions; incomplete discovery raises rather than assuming absence |
| Cross-group same-ID overwrite/race | Memory raises until release. Table uses one local identity/sync lock, complete discoverable-partition ownership checks and a 4,096-active/uncertain-owner cap, with rejection instead of eviction. No per-ID lock cache. | Simultaneous same-ID/different-group requests in both stores: one accepted, one typed error; release allows new owner; multiple persisted owners rejected; capacity rejects without eviction |
| Stream close/cancellation suppresses financial cleanup | `cleanup.py` independently starts shielded credit/quota/metrics tasks before context close. Each gets five seconds, cancellation join at most 0.1 seconds; repeated caller cancellation cannot cancel their opportunity. Non-cooperative tasks remain tracked at a 64-task cap, never unboundedly detached/evicted. Errors/timeout propagate with other failures retained as notes. | Close exception still settles actual credit and quota/metrics; repeated cancellation during blocked settlement; successful cleanup then cancellation propagates; close+credit timeouts, conservative recovery and no leaked cooperative tasks; non-cooperative close bounded join and capacity rejection without eviction |

New `tests/unit/test_credit_recovery.py` has **27 fault cases**. Two real Azurite tests were added to
`tests/integration/test_azurite_distributed_state.py`. Existing memory-expiry and Table-outage tests
were updated for the independently approved changed contract. FakeTableClient now prevalidates
Create operations and reservation Delete ETags before applying a batch, making the race tests atomic.

## Exact verification

| Check | Result |
| --- | --- |
| `.venv/bin/python -m pytest tests/unit/test_credit_recovery.py -q --disable-warnings` | **27 passed** |
| `.venv/bin/python -m pytest tests/unit/test_credit_recovery.py tests/integration/test_azurite_distributed_state.py tests/unit/test_table_client.py -q --disable-warnings` | 47 passed at intermediate checkpoint; later four fault cases included in full suite |
| `.venv/bin/python -m pytest -q --disable-warnings --cov=foundry_router --cov-report=term-missing --cov-fail-under=80` | **428 passed**, no skips, **90.08%** coverage, 33.00s; all **11 Azurite tests** executed |
| `.venv/bin/ruff check src tests` | Passed |
| `.venv/bin/ruff format --check src tests` | 47 files already formatted; all source edits via apply_patch |
| `.venv/bin/mypy src` | No issues in 25 source files |
| `git diff --check` | Passed |
| `docker build -t foundry-router:credit-recovery .` | Passed; Python 3.12/Azure extras; manifest `sha256:9b9aba6b62ec799f99640e62a1de6390562e3bb396c00da3429822b7ac3b389d` |
| Documentation link validation | Feature-scoped local Markdown checker passed: **122 local links in 19 Markdown files** |
| Sonar | `scripts/quality/sonarqube-scan.sh` absent; not run |

Azurite ran in the session-owned `foundry-router-credit-recovery-azurite` Docker container using
`docker run -d --rm --name foundry-router-credit-recovery-azurite -p 127.0.0.1:10002:10002 mcr.microsoft.com/azure-storage/azurite azurite-table --tableHost 0.0.0.0 --skipApiVersionCheck`.
The test fixture created/deleted random isolated tables. Tests ran under local Python 3.14.7 with
dependency deprecation warnings; Docker builds the configured Python 3.12 runtime.
The session-owned emulator was stopped with `docker stop foundry-router-credit-recovery-azurite`;
`--rm` removed it. Final feature diff/status were reviewed; only shared-credit related source,
tests and documentation changes are present, with no operator-local input overwrite.

## Contextual review and boundaries

The implementing session revisited `.agents/prompts/deep-review.prompt.md` scope against all five
faults: financial intent/reaper races, ambiguous commits, membership publication, cross-partition
identity and generator cancellation. Tests were driven by exact independent failures, not just
return-value coverage. The original implementing-session review missed these findings; its earlier
completion claim is superseded by this recovery work. Independent implementation re-review remains
pending and is not substituted by plan approval.

Local serialization intentionally trades parallel admission throughput for clear ownership. Shared
Table accounts still use cross-replica ETag transactions, but there is no distributed same-ID index:
server-owned unique request IDs and drained consistent writer rollout remain mandatory. Memory
restart still loses estimates/intent. Conservative legacy/pre-egress expiry can overestimate spend;
later reconciliation may correct it. Non-cooperative dependency cleanup cannot be force-terminated
by Python: bounded tracking prevents growth and fails closed at capacity until tasks complete.

No production deployment, commit or push occurred; operator-local production inputs were untouched.
Production remains memory-backed with one replica. Real production shared-credit inference/load and
multi-worker metrics aggregation remain unverified.
