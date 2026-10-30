# G1 resume Inputs

## Required Inputs

| Input | Source | Owner |
|---|---|---|
| Previously approved G1 finish plan and runner | [`g1-ready-finish`](../g1-ready-finish/packet.md) | Coordinator |
| Original e/a/D ledgers, approved initial packet, and ready evidence | Approved private base described in [`handoff.md`](../handoff.md) | Coordinator |
| Partial-run consumption and case 0/1 result artifacts | Original e and finish b directories under the private base | Coordinator |
| Read-only case-2 settlement reconciliation, schema `g1-ready-finish-case-reconciliation-v1`, SHA-256 `63f861c42e0c10865aa50da8135f2d5f8a8fed9b7548bec03e9173cfc8067cc3` | Private finish b directory; no account values are committed | Coordinator |
| Current executor-only Allow, one approved ready Table revision/worker, and public readiness 200 from the executor address | Fresh read-only Azure CLI/HTTP observation after the stopped apply | Operator |
| Original unstarted case-3 slot and its original program allocation | Original private program ledger plus absence of case-3 markers | Coordinator |

## Optional Inputs

- None. Missing or changed financial, case, ownership, or ingress evidence blocks continuation.

## Input Validation Checklist

- [x] Original run stopped without retrying or replacing a consumed slot.
- [x] Case 2 has immutable HTTP/usage artifacts and a separate same-process settlement reconciliation.
- [x] Case 3 remains unstarted; no new program allocation or budget amendment is proposed.
- [x] Current ingress is executor-only `/32` Allow; total remaining ingress mutation is one DENY, with no second Allow.
- [ ] A fresh continuation packet and exact independent approval bind current source, reconciliation, state, budget, and the one remaining case.
