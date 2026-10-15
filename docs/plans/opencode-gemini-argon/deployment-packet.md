# Argon deployment packet

Status: **Planned**. No remote image push, inference, secrets/grants, restart or rollout performed.

[Configuration delta](configuration-delta.json) adds one explicit pool/backend and
account-owned credit policy. `${OPENCODE_CREDENTIAL}` is an external substitution
marker; it is not a literal deployable credential. Existing production values
must be merged from a fresh captured coherent versioned bundle, without changing
existing pool/alias/member/price/auth/ingress settings. The reserve is proposed and
requires the pending operator allocation decision. Cycle and remaining estimates
are required inputs, not guessed balances.

[Acceptance manifest](acceptance-manifest.json) specifies four distinct one-shot
slots with exact request hashes/model/low-thinking/token/time bounds. A runner
must bind this manifest to the reviewed immutable Linux image digest and full
config-bundle hash, atomically consume a durable slot before egress and refuse
replay or ambiguous prior state. Its runner implementation/review and immutable
image/config binding remain Planned. The maximum configured estimate for 128
output tokens is $0.00256 per request plus bounded estimated input; this does not
claim a measured provider bill or provider-enforced spend ceiling.

1. Confirm closed production intake, fresh account allocation/reserve, cycle and
   existing all-account seeds. Resolve credential only in process memory.
2. Prepare a fresh isolated staging writer with its explicitly allocated OpenCode
   estimate. Keep the existing Azure staging app stopped with its stale seeds.
3. Bind the verified image/config/manifest and review the packet and bounded
   runner. Execute staging nonstream then stream once; halt on any failure.
4. Stop all staging writers, confirm zero reservations, capture conservative
   transfer estimate. Reconfirm production quiescence and zero reservations,
   then stop its old writer before a promotion can start.
5. Promote tested immutable image and merged coherent pinned secrets with fresh
   all-account initial credit. Execute production slots once, check terminal
   text/usage/settlement/cleanup and fresh liveness/readiness/admin policy.
6. Preserve previous image/config bindings for recovery. A rollback also needs
   quiescence and fresh balances; do not reactivate a stale memory revision.

## Current read-only production binding

Azure query on October 13 returned provisioning `Succeeded`, ready revision
`foundry-router-production--or-two-20261012`, one maximum replica and the
[recorded release image](../openrouter-production-two/deployment-evidence.md).
Private account IDs/secret version mappings stay outside this packet.
The new OpenCode provider is not in that running image.

## Remaining inputs and gates

- Operator confirmation of closed intake and fresh OpenCode allocation/reserve.
- Fresh quiescent all-account estimates and explicit cycle/allowance inputs.
- Reviewed durable runner and exact Linux image/config binding.
- Live staging protocol/model/account compatibility and streaming qualification.
- Promotion plus exact production acceptance and credit handoff.
