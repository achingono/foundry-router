# Pricing-estimation 503 evidence

Status: Implemented and deployed; guarded handoff, no-egress acceptance and ingress restoration passed.

- Live read-only diagnosis: loaded Terra pricing USD/M 2.5 input / 0.1 cached / 7.5 output and ready=true. Healthy Terra candidates had both successful and rejected requests in the same process. The exact supplied ID was outside the retained log sample; exact-body cause remains inference.
- Local reproduction: a 2,010,078-byte synthetic request passes the 2,097,152-byte intake limit but previously failed the separate 2,000,000 bound with None, producing pricing_unavailable/503.
- [Plan review](plan-review.md) approved before implementation. [Independent contextual review](implementation-review.md) found no Critical/Major defects. Sonar script is absent; no scan pass claimed.
- Focused original run:130 passed. Added exact-intake-cap API forwarding and checked missing-media-price regressions address both review suggestions; expanded focused result:132 passed (including exact-cap actual intake/forwarding and missing media price with valid token prices).
- Full suite:2,884 passed,3 skipped,19 deselected;90.45% coverage. Sandbox run was interrupted because local loopback tests were blocked; unrestricted complete run passed. Logs remain private temporary files.
- Ruff lint/format pass across repository; Mypy passes76 source files.15 real Azurite tests pass against a temporary emulator.
- Docker native build passes. Synthetic Docker health/live and ready both return200; just-over-2M input with invalid max_output_tokens returns422 request_estimation_unavailable with zero debit/reservations. No provider inference.
- Default/configured intake, pools, prices, auth, media profiles and streaming behavior are unchanged by the code fix. Known request failures are distinct from missing token/media prices; old estimator wrapper preserves None semantics for settlement callers.

Production handoff and acceptance completed as recorded below. No user prompts, model outputs, image data or credentials are recorded in repository evidence.

## Production outcome

Independent [final packet review](packet-review.md) approved the exact script before mutation. ACR build cab promoted immutable digest `36d453f80c2fd8af990eab43f9030c3da1e0992b247aaaf742b31aff9c3bcea4` as sole healthy revision `foundry-router-production--pricing-20261029`. Production remains memory-backed, single worker and maximum one replica.

Public intake denial, same-process drain and absent old replicas were verified before promotion. All four account seeds came from fresh drained remaining estimates, floored to six decimals with no refund/replenishment. All16 existing vault references were already versioned and stayed identical; one new version-pinned seed secret was written. No role grant or infrastructure resource was added.

Loaded environment hashes,22backends/14pools, aliases, pricing, reserve/cycle policies and command hash matched the baseline; fresh seeds loaded exactly, debit/recovery counters started at zero and no reservations remained.

The no-egress synthetic Terra acceptance sent 2,010,079 actual bytes, including2,010,000ASCII input characters and empty tools. It passed the formerly failing estimation step, then returned HTTP422 `request_estimation_unavailable` explicitly for invalid boolean max_output_tokens. Public readiness was200/ready=true. Same-process post-acceptance comparison proved all credit groups unchanged, zero debit and no active reservations. No paid inference or provider giant-input acceptance was claimed.

Exact original ingress policy was restored. Final guard verified same process, sole healthy revision and public readiness200/ready=true. Public traffic may change the local estimates after restoration. The exact historical user request body is unavailable; the reproduced bound mismatch is fixed and other known request-estimation failures now receive clear422 validation responses.

[Final independent review](final-review.md) approved the deployed claims and artifact reconciliation with no unresolved Critical/Major findings. Final source hashes match the built release. Relative documentation links and whitespace diff checks pass. Temporary Docker and Azurite verification services were stopped; the unrelated request-limit plan was preserved.
