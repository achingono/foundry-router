# Remaining three Major findings — implementation evidence

## Status: Implemented (local verification); production deployment Planned

The operator approved [the follow-up amendment](follow-up-amendment.md) under the existing reviewed
failure contract; it was recorded before fixes. Independent implementation re-review subsequently approved all scoped fixes, replaying the three prior failure scenarios and running 125 focused tests successfully.

## Completed fixes

1. `state/table.py`: incomplete initialization/config merge raises `TableEntityCreditStoreError`.
   Old aliases and attempted partitions remain discoverable for recovery, but new-settings routing
   stops at the typed failure. Failed Settings are not cached; the same object succeeds after storage
   recovery. Existing missing/invalid settings tests now assert explicit failure, not silent skip.
2. `state/table.py`, `reconciliation/`: `reconcile_tracked_ownership()` scans the bounded tracked-ID
   set under the local store lock. It checks every known partition and retires only confirmed absent
   or finalized ownership. Live, ambiguous and incomplete discovery retain tracking and capacity
   constraints. Periodic maintenance runs before the balance provider, including provider outages.
3. `forwarding/`: after meaningful stream output, credit settlement always charges the reserve
   unless valid known usage supplies actual cost (including zero). HTTPError/502 does not create
   zero intent. SSE error/metrics and no-failover behavior remain intact. The prior main test that
   required no worst-case charge on midstream failure was incorrect and is explicitly corrected.

Azurite concurrent initialization exposed `ResourceExistsError` without an EntityAlreadyExists
code. `state/azure.py` now confirms the requested entity exists before treating that SDK create race
as existing-row rejection; an absent row or failed read still raises. A dedicated unit regression
checks confirmed vs unconfirmed behavior.

## Tests and exact verification

New `tests/unit/test_credit_follow_up.py`: **13 tests** covering wrong-group zero-egress/same-Settings
retry, SDK create-race confirmation, timeout without commit, other-writer recovery, reaper lost
acknowledgement, finalized retirement, provider outage, incomplete/ambiguous discovery and capacity,
and memory/Table post-output errors with absent/known/zero usage. Added three real SDK/Azurite tests.

| Check | Exact result |
| --- | --- |
| Focused lifecycle suite | `.venv/bin/python -m pytest tests/unit/test_credit_follow_up.py tests/unit/test_credit_recovery.py tests/unit/test_table_concurrency.py tests/unit/test_shared_resource_credit.py tests/unit/test_main.py tests/unit/test_reconciliation.py -q --disable-warnings` — 199 passed at focused checkpoint |
| Follow-up plus real Table tests | `.venv/bin/python -m pytest tests/unit/test_credit_follow_up.py tests/integration/test_azurite_distributed_state.py -q --disable-warnings` — **27 passed** |
| Full suite | `.venv/bin/python -m pytest -q --disable-warnings --cov=foundry_router --cov-report=term-missing --cov-fail-under=80` — **444 passed**, no skips, **90.14% coverage**, 6.57s; all **14 Azurite integration tests** executed |
| Ruff | `.venv/bin/ruff check src tests` — passed |
| Formatting | `.venv/bin/ruff format --check src tests` — 48 files already formatted; edits via apply_patch |
| Types | `.venv/bin/mypy src` — no issues in 25 source files |
| Whitespace | `git diff --check` — passed |
| Docker | `docker build -t foundry-router:credit-follow-up .` — passed; manifest `sha256:8316d5e6de143f757801016ad9c74c7f7157d599100aea3f026ac35546ad1efa` |
| Sonar | `scripts/quality/sonarqube-scan.sh` absent; not run |
| Relative links | Feature-scoped checker passed: **131 local links in 21 Markdown files** |

The full-suite first run exposed two remaining legacy incomplete-config expectations; corrected
tests then passed in the final full run. No source change followed the successful Docker build.
Local Python is 3.14.7; dependency deprecation warnings did not fail checks. Docker uses Python 3.12.
Azurite used a session-owned container `foundry-router-credit-follow-up-azurite` with loopback port
10002, `--rm`, `azurite-table --tableHost 0.0.0.0 --skipApiVersionCheck`; tests created/deleted random
isolated tables.
After verification, `docker stop foundry-router-credit-follow-up-azurite` stopped the session-owned
emulator and `--rm` removed it. Final feature diff was inspected for failure/ownership transitions,
unsupported deployment claims and secrets; no local production input overwrite occurred.

## Contextual review and boundaries

Implementing-session review followed `.agents/prompts/deep-review.prompt.md` scope: failed sync must
not be success at the routing boundary, absence requires complete discovery, capacity must recover
without eviction, and post-output status cannot infer free provider work. Faults demonstrate actual
balances/reservations/egress, including real SDK transactions. Independent re-review may follow.

Periodic tracked-ID discovery is bounded by the existing owner limit but costs reads across known
partitions and holds the local store lock; SDK reads retain their configured timeout. It does not
invent distributed request identity or replace drained migration. Caller-supplied unique server-owned
IDs remain required; discovery cannot prove unknown partitions outside consistent configured history.

No production deployment, commit, push or operator-local input edit occurred. Production remains
memory-backed with one replica; live inference/load, authoritative reconciliation and independent
production deployment validation remain separate gates.
