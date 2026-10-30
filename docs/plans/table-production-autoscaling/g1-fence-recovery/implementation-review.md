# G1 fence recovery independent implementation review

Date: 2026-10-30. Reviewer: independent GPT 6 Astra subagent session, separate from the recovery developer (Sol) and executor. Owned file: this review only.

## Verdict

**Ready for read-only preparation and independent exact-packet review. Unresolved Critical: 0. Unresolved Major: 0.**

The reviewed implementation satisfies the [approved plan](plan-review.md) for advancing only the original four unstarted G1 slots under a new single-use recovery identity. This contextual verdict is not executable approval or evidence of successful Azure recovery. Fresh full-verifier completion and actual private preparation/exact approval remain the existing gates before apply; no additional user authorization is requested.

## Exact reviewed files

| File | SHA-256 |
| --- | --- |
| [Recovery runner](../../../../scripts/quality/table_production_acceptance_recovery.py) | `e3c47d6c7b7634c5578032df06795d4363205804f475d58d80f4560e7c8b6f45` |
| [Recovery tests](../../../../tests/unit/test_table_production_acceptance_recovery.py) | `762df8cb9e932ada219c1afe6b7b709c9e2dc4438cde732bcf6a5b041ef1f887` |
| [Operational packet](packet.md) | `3597d7244f46eedc4e6750d76b2855986acfd006900b0b19e9ceddc56037d532` |
| [Frozen G1 helper](../../../../scripts/quality/table_production_acceptance.py) | `701cca098ce005703cc97d298adde7c7072e61ce8bf233b0f941c815ffa7e922` |
| [Frozen G1 tests](../../../../tests/unit/test_table_production_acceptance.py) | `04b79e5fea57bb527dbf4015d401aff59697069dfa3c7fc2aee66851585e2a8b` |

## Contextual findings and acceptance reasoning

No blocking findings identified under the repository's [deep-review scope](../../../../.agents/prompts/deep-review.prompt.md).

- **Known unused-slot proof is substantive.** `history()` pins the exact original prepared hash, verifies original approval/outer consumption/ledger/proposal binding, requires the precise `stopped_unverified` / `Fence denial unproved` failure and rejects any case, drain, stop, promotion, restart, result or conflicting journal. The frozen original apply raises that reason immediately after its initial fence observation, before drain/stop or any paid dispatch. Thus this is a specific known-stage recovery, not reclamation based only on absent case files. Original apply is never invoked.
- **Original financial ownership survives.** Original execution, canonical program and recovery-directory locks span apply. Exclusive fsynced original-program `recovery-consumed.json` precedes mutation and prevents another recovery directory from taking the slots. Original ledger/approval/consumed/failure/proposal bytes remain hash-checked and unchanged; only previously absent linked stage/case/result records are appended. A partial marker, timeout or uncertain dispatch cannot replenish the program or authorize another case attempt.
- **Bounds remain the original bounds.** Four original cases retain their exact model/backend/pricing identities, USD 0.00448 each / USD 0.01792 total reservation, max128 output, max64 reported input, zero successor retries and one backend per model. The original USD1/16-attempt program is not recreated. Unknown paid outcomes preserve consumption and stop later slots. These are local liability estimates, not authoritative Azure balances.
- **Cold min0 is an explicit conditional branch.** Prepare may defer account proof when no old worker exists. After exact approval and durable recovery consumption, apply may make only the bound executor-only warming change, then require old configuration/pins/environment/command, sole worker, unchanged original accounts and zero new request counters. The changed baseline is recorded as old-image warming, explicitly not current-image restart acceptance. Once established, the same baseline must survive fence/drain; there is no implicit reset or further rebaseline.
- **Propagation and deadlines address the original failure.** Public observation waits for desired403 or200/ready under an enclosing asynchronous deadline covering headers/body and bounded repeated GETs. Expected startup/propagation statuses can wait rather than immediately fail. Worker observation includes nested CLI work in its remaining180-second budget. Main-thread `Budget.call` supplies an enclosing alarm for synchronous frozen helpers, reserves eight seconds for their bounded cleanup, rejects conflicting timers and restores handler/timer state. Azure subprocess timeouts kill only the owned process group and bound final collection. The sequence has no concurrent worker/thread sharing this alarm state.
- **Timeouts cannot turn incomplete evidence into success.** Dispatch persists HTTP/terminal numeric observations before subsequent financial snapshots; a stream terminal alone is not clean EOF. A deadline during dispatch, marker creation or a financial snapshot unwinds execution, retaining existing consumed records and preventing later slots/results. Snapshot cleanup does not resume settlement after an exception. The restored alarm state and timeout failure path have direct local tests; no Azure timing guarantee is inferred from mocks.
- **Old writers cannot overlap promotion.** Recovery uses the corrected frozen `writers(allow_draining=True)` only for absence observation: all revisions must be inactive and every replica, including inactive draining replicas, remains counted. Promotion cannot occur until the aggregate is empty. Strict sole/active-writer checks remain for snapshots and readiness. The original approved template-only REST body is revalidated and sent by private `@file`; secretRef-only entries are preserved without the previously rejected high-level CLI normalization.
- **Every financial step is chained.** Old legacy debit/recovery omissions represent the established historical zero baseline only. The successor must expose current fields explicitly and match the original account map. Each case's before map must equal the last accepted map; its after map must show the price-matched debit/counter delta, unchanged other groups/cycles/recovery and zero reservations. Accepted state is persisted before another slot. Tests specifically reject between-case drift and missing current counters.
- **Restart acceptance is separate and actual.** Four paid passes precede final DENY403, quiet100-second same-process drain and one consumed restart. Acceptance requires changed actual replica/container generation or increased restart count, changed process identity on the same approved revision, ready effective configuration and unchanged persisted account/counter state. Cold warming cannot substitute for this stage, and no extra inference is authorized.
- **Staged completion is accurately represented.** Linked original/recovery results explicitly say original apply did not complete and leave DENY/min1/max1 with separate original-ingress/min0 cleanup outstanding. The packet identifies ongoing minimum-replica cost and requires the later production prerequisite reader to verify actual linked four-pass/restart evidence. Neither this review nor file presence clears production migration/autoscaling gates.

## Independent evidence

- Inspected current git status, all recovery plan/packet/test/runner files, relevant canonical operations guidance, the original exact review and the frozen helper's history, transport, writer, promotion, accounting and dispatch paths. Existing unrelated source/document changes were treated as other writers' work.
- Under the available original `e` execution lock, independently ran the new runner's **local-only** `history()` against the original private directory. It passed with exactly the eight original base files, four original cases and USD0.01792 aggregate reservation. No recovery guard or started-stage/case journal existed at that observation. This check neither created a recovery marker nor changed original bytes.
- Independently ran local-only `release_binding()` against that original packet: full runtime/image-metadata/helper/test provenance matched. This is stronger than assuming the dirty working tree is incompatible or silently reverting user work.
- Independently reran `.venv/bin/python -m pytest tests/unit/test_table_production_acceptance_recovery.py -q --no-cov -p no:cacheprovider`: **36 passed**, 15 dependency deprecation warnings, 0.50 seconds. No shared coverage database was written by this run.
- The developer's 98.18% recovery coverage and the concurrently delegated full verification are not relabeled as reviewer-observed results. Their final evidence must be checked at exact approval. No Azure command, network request, prepare/apply, inference, source/test modification, Docker build or private approval creation occurred in this review.

## Next existing gate

Proceed with read-only preparation. Independently review its actual private hash chain, fresh live bindings, executor exit/address and conditional cold-baseline disposition, final verifier results and continued dedicated-resource identity disjointness. Only that exact approval can authorize the single-use apply. Retain the paused-writer handoff and separate staged-cleanup disposition already specified in the packet.

### Subsequent exact review

The new `a` recovery preparation and completed final verification have now been reviewed in the [exact-packet review](exact-packet-review.md). That separate verdict approves the bound single-use recovery, including controlled cold warming with mandatory original-state equality before stop or paid calls. The implementation hashes above remain unchanged; the earlier pending-verification statements describe the initial contextual review, not the final exact disposition.
