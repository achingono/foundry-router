# Production estimation correction packet

Status: Executed after independent final packet approval; acceptance and restoration passed. See [evidence](evidence.md).

User authorized investigating and resolving production Terra High failures. This packet deploys the independently reviewed code correction, preserves current pricing/pools/auth, and performs no paid inference. Current operator uses existing vault/application permissions; no role grant or infrastructure resource is added.

Release: ACR build cab, Linux/amd64 immutable digest `36d453f80c2fd8af990eab43f9030c3da1e0992b247aaaf742b31aff9c3bcea4`. Source hash aggregate: `ff0d1a74c3bb226b7faa13f6e3457580718aa28ab4a2d4c10f92509989eaed4d`. All source Python files, Dockerfile and pyproject are hash-bound. Full source verification passed;132 focused tests include two review additions, full suite2884pass/90.45%,15 real Azurite tests, Ruff/Mypy and native Docker health/no-egress acceptance pass. Sonar script absent. No source edits after release build began.

Exact executable `/private/tmp/router-pricing-503-handoff.py` SHA-256 `4f3017206f3be8060ad288a2501ab0628eb90d90e2e5f3c3871546031d6909c8`; dedicated helper SHA-256 `88349d8287ebef603bf2f982a8e1bca299e8162b27d27ec9c067c75a01858f07`. Baseline app hash `0cb83a382f8a5e8efc15b32c0a568c1123560c770463878244ba87cca34f5b45`; baseline snapshot hash `2037af245abc762fb3f1d3979e41f8cba77bd6850a5df146e94580abf4452ec1`; secret-binding hash `233d7714c4958580bca878392599251e66ca0afd589e7d079d4f58b035394089`. Private artifacts live in `/private/tmp/router-pricing-503-handoff/`. Full resource identity and pinned subscription are verified by helper; environment-specific IDs remain private. Four mocked invariant/config drift refusal checks passed.

Loaded environment hashes for every configured entry match resolved current secret versions and literal settings. Pin existing secret references to these same effective versions at promotion (0 unversioned reference URLs become versioned); do not rotate values. Apply-time keys and intake configuration read prepared versions. Single revision, memory state, maximum one replica, no command/args override or worker-count environment override are mandatory. Identical single-worker image entrypoint and server command hash are checked.

## Ordered execution

1. Acquire exclusive execution lock; validate all prepared/source/script/helper/baseline/secret pins. Execution is consumed before mutation and cannot be replayed.
2. Replace ingress restrictions with deny-all; prove public403 and unchanged old configuration/process. Wait past the configured intake deadline plus5seconds, then repeated quiet same-process snapshots. All reservations must be zero. Capture fresh estimated remaining per account, floor to six decimals, no refund or extra allowance. Snapshot and seeds are hash-bound.
3. Set one new versioned initial-balance secret and re-read it. Revalidate unchanged drained state, barrier and all existing pinned secrets. Deactivate old revision and prove no old active revision or replicas before promotion.
4. Promote immutable reviewed image with same template/pools/auth/pricing, existing same-value version-pinned references and fresh seed reference; revision suffix changes. Verify sole healthy revision, unchanged loaded settings and all configured environment hashes except fresh seeds, exact fresh seed hash/balances, zero new debit/recovery counters, no reservations, memory/one and unchanged command hash.
5. Restrict ingress to the bound executor IPv4. Verify same process and credit groups. Consume exactly one synthetic no-egress acceptance slot before dispatch. Send Terra Responses with2,010,000ASCII input characters, empty tools, boolean max_output_tokens. It must pass estimation then return422 request_estimation_unavailable mentioning max_output_tokens; old estimator returned503 earlier. Record actual transmitted byte count, readiness, and unchanged credit/no reservation. No retry, paid provider call or giant-input provider acceptance claim.
6. Restore exact original ingress, verify same process/configuration, sole healthy writer and public readiness. Account estimates can change after restored public traffic.

## Failure and recovery

Any ambiguous mutation or acceptance consumes the execution identity. Stop and inspect actual Azure/configuration/process/ledger read-only; do not reset execution markers, replay apply/inference, reload stale seeds, automatically reactivate the prior revision or refund a debit. Retained deny/executor restrictions and a stopped writer may require a fresh independently reviewed recovery packet. Recovery must reconcile actual current state and preserve balances before reopening intake. Exact restoration remains mandatory to close the task.

This is an operational source correction, not production Table cut-over. Existing pricing is local estimated cost; it is not an Azure balance or provider-billing guarantee. Exact original-body causation remains inferred from the reproduced defect; historical request bodies were not retained.
