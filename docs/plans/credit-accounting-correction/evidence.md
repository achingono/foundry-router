# Credit accounting correction evidence

Status: **Implemented and deployed** in production memory/one mode. Production readiness, guarded credit handoff and scoped acceptance settlement passed; exact streaming token receipt and live nonzero-cache validation have the limitations below.

- [Plan review](plan-review.md) approved the change before coding. The delegated build session stopped before edits because its provider balance was exhausted; coordinator implementation under the same approved plan was independently reviewed.
- [Implementation review](implementation-review.md) passed with no Critical or Major findings.
- [Verification](verification.md): 2,805 passed, 3 skipped, 19 deselected; 90.39% coverage. Ruff lint/format and mypy passed; 15 real Azurite tests and native/linux-amd64 Docker builds and health checks passed.
- SonarQube script `scripts/quality/sonarqube-scan.sh` is absent: not applicable, not a scan pass.
- [Pricing review](pricing-review.md) approved conservative USD ceiling rates from exact Azure retail meters, including existing priority processing exposure. Historical usage records matched current-cycle CAD costs; they do not establish a current authoritative USD balance.
- [Production packet](production-packet.md) records immutable release digest, configuration pins and guarded handoff. First packet review identified three Major operational guard/budget gaps; revised executable includes repeated barrier/configuration checks, hash-bound diagnostic/state artifacts and USD 0.021 worst-case acceptance budget. No production mutation preceded re-review.
- Current operator has existing vault-scoped write permissions; no temporary grant is required.
- Prior investigation documentation and unrelated responses-request-limit plan are preserved.

## Production execution

Independent [packet re-review](production-packet-review.md) approved the corrected
script before mutation. Public intake denial and unchanged old process were proven;
all reservations drained. Inherited seeds were floored conservatively:
fs-swarm USD 11.748851, opencode-account USD 9.90, or-shared USD 4.81.
The operator-authorized openclaw seed is USD 128.24. Snapshot digest:
`689bf2986c8048f76020dca9952e5caf8e5f5839d4dcafbec84c41e80e6b3b3c`.
No historical debit refund was applied. Promotion passed; final acceptance/restoration outcomes are recorded below.

The old revision was deactivated and empty old-writer/replica listings were
verified before promotion. Release build `ca8` is running as sole healthy revision
`foundry-router-production--credit-20261029`, memory-backed with maximum one
replica. Image digest:
`sha256:080491a7df64a42f8eed30d37ba0a67d218f1d3a6e6b48aee0f50c473bc6d273`.
All 17 backends, 11 pools, aliases, reserve policies and cycle dates were checked
against the pre-handoff configuration. All four groups loaded their exact seeds;
new debit counters started at zero. Openclaw allowance USD 142.49, estimated
remaining USD 128.24 and post-reserve availability USD 118.24 were verified.
Three new monetary secrets were version-pinned and their values re-read before
promotion; authentication secrets were preserved. No role assignment was created.


The non-streaming acceptance returned completed usage (10 input, 5 output,
zero cached tokens), with exact USD 0.000125 settlement. Streaming reached the
completed terminal and usage checks, but its post-call diagnostic snapshot was
throttled by Azure WebSocket HTTP 429. No public acceptance slot was replayed.
The already-launched read-only diagnostic retry succeeded and verified the same
process. Its metrics showed exactly two successful sol requests, USD 0.000250
request cost and matching canonical debit, no recovery debit and no active
reservations. The lost exact streaming token receipt remains unavailable.
[Recovery packet](recovery-packet.md) describes a fresh guarded reconciliation and
ingress restoration; independent approval and final restoration passed.


## Final production acceptance

[Recovery review](recovery-review.md) approved the exact settlement/restoration
amendment. Fresh process/configuration/admission guards and independent request
cost-to-canonical-credit reconciliation passed. Non-streaming exact usage/debit
passed; streaming completed terminal/usage validation reached and USD 0.000125
settlement was recovered from the isolated two-request aggregate, without
inventing its lost exact token receipt. Original consumed stream slot remains
consumed; a separate recovered-settlement receipt records the limitation.
Actual pair request-cost and ledger debit: USD 0.000250, within the reviewed
USD 0.021 retry/failover-aware budget. No recovery debit or duplicate charge.

Original ingress restrictions are restored. Its first immediate readback was
stale during Azure's asynchronous update; read-only finalization verified empty
restrictions, provisioning `Succeeded`, the exact promoted fingerprint/pricing,
and unchanged process identity. No duplicate mutation was submitted.
Public `/health/ready` returned ready=true with all nine checks passing.
Final openclaw estimated remaining USD 128.23975, available USD 118.23975;
all other groups retain the drained seeds. Public traffic can change these local
estimates after this capture. Production remains memory-backed, maximum one
replica. Table production cut-over and a live nonzero-cache discount are
unverified; cached-input and recovery accounting have unit/real-Azurite coverage.

No historical local estimate was refunded. Azure actual billing evidence is
lagged and in CAD; the configuration and counters are USD local estimates.
The independent reviews, full verification and final documentation checks
are linked above. No credentials or provider outputs are stored in repository
release evidence; environment-specific executable artifacts remain private.

Final documentation validation: 24 changed/related Markdown documents had no
broken relative links; `git diff --check` passed. Final source diff review found
no embedded environment identifiers or credentials; source remained frozen
through full verification, release build and production acceptance.

[Final independent review](final-review.md) approved the evidence and deployed
claims, including unchanged process, restored ingress and scoped receipt limits.
