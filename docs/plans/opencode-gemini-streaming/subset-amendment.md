# Subset funding amendment: Flash/Argon/Sonnet qualification

Status: **Planned** pending independent review. Operator deploy order covers fresh funds; this amendment records the authorization explicitly rather than assuming it.

## Scope

Subset identity `opencode-zen-five-subset-20261014`: ten immutable slots, five staging then five production — Flash nonstream/stream (512), Argon nonstream/stream (512), Sonnet nonstream-only (128). Grok/Muse excluded on the recorded Grok over-bound failure (`staging-3-nonstream`: HTTP 200, exact debit, 532 output over the 512 bound) and unconsumed Muse slots; no substitution, no replay of consumed `STREAMING_RUN` slots. Staging re-runs the five already-passed cases under fresh slots (~$0.002 expected at observed usage).

## Seed arithmetic (observed inputs, not estimates)

Worst-case reservations with observed input counts (Flash 7, Argon 38, Sonnet 18):

| Case | Reservation USD |
|---|---|
| Flash nonstream/stream | (7×1.50 + 512×7.50)/1M = 0.0038505 ×2 = 0.007701 |
| Argon nonstream/stream | (38×4.00 + 512×20.00)/1M = 0.010392 ×2 = 0.020784 |
| Sonnet nonstream | (18×4.00 + 128×10.00)/1M = 0.001352 |
| **Five-case total** | **0.029837** |

Required: 0.029837 + 0.05 reserve = 0.079837. Authorized fresh **R_sub = S_sub = 0.09** (no diagnostic debit in this identity), margin 0.010163. The stopped staging writer's 0.0867455 remainder is discarded, not carried forward. Production OpenCode seed fixed at **9.90**; production five-case worst ≈ 0.029837 against 9.90 with the same 0.05/5% reserve.

## Provenance

Fresh isolated staging funds only, under the operator's standing allocation authorization and explicit production-deploy order. No borrowing from production, no transfer of prior unused staging, no reuse of discarded amounts. These are local cost estimates, not provider balances.

## Gates

Independent review of this amendment and the harness identity, offline tests and verification, staging packet review binding the ca7 digest, then live staging. Production promotion keeps all existing pools/aliases/auth, memory/one, and the inherited barrier/drain/handoff gates with reconciled existing seeds plus OpenCode exactly 9.90.
