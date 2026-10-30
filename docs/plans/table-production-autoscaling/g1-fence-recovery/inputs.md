# G1 fence recovery Inputs

## Status: Planned

Direct authorship by the disclosed planner fallback, 2026-10-30. This amendment covers only the existing isolated G1 app and its four verified unused paid slots. User authorization includes bounded recovery/cost judgement; independent plan and exact-executable approval remain gates, not a new user authorization request.

## Required Inputs

| Input | Source | Owner |
| --- | --- | --- |
| Workflow/one writer | [AGENTS.md](../../../../AGENTS.md), [agents](../../../development/agents.md) | Coordinator |
| Original approved scope | [G1 packet](../phase1-packet.md), [exact e review](../phase1-exact-packet-review.md) | Independent reviewer |
| Frozen helper verification | [Verification](../phase1-verification.md), [implementation review](../phase1-implementation-review.md) | Verifier |
| Consumed e execution history | Private approved `table-prod-g1-20261030-e/`: prepared/approval, consumed marker, program ledger, proposal and binding, failure record | Executor; never overwrite |
| Current recovery observation | Coordinator reports public403, same old Table process/image, unchanged two accounts, zero case markers and no stop/update/restart or old-drained markers; refresh under lock | Executor |
| New recovery binding | New owner-only directory, recovery identity, executable/test/helper/source hashes, exact allowed operations, original-ledger/artifact hashes and current app/secret/process/account projection | Recovery developer/executor |
| Independent review | Astra session separate from author; plan, contextual implementation and exact packet verdicts | Coordinator/reviewer |

Original packet SHA-256 is `721fc9be3e5a862741e3c71eaa327dc8c0e153c789ee0a17029af4ee13a9e8de`; frozen helper is `701cca098ce005703cc97d298adde7c7072e61ce8bf233b0f941c815ffa7e922`. Target approved image is `sha256:36d453f80c2fd8af990eab43f9030c3da1e0992b247aaaf742b31aff9c3bcea4`; observed old image is `sha256:78c5d570d64eacfdcad02c8c8c21c46a4db24af2c4ce944c687a01c99410fb6a`. Proposal semantic hash remains `8d27348edaac731e67129785a2a5b85c93546fbd803eebad6215a76e68646a2c`. These documentary pins must be recomputed, not trusted by prefix.

Financial scope is unchanged: original program USD1/16 upstream attempts; recovery may consume only the original four slots, USD0.00448 each/USD0.01792 aggregate reserved estimate, max128 output, zero retries, one backend per each of two selected models/accounts on the dedicated test resource. No new liability allocation, production inference account coverage, Table seed/reset, infrastructure/RBAC, other-provider call or production mutation.

## Optional Inputs

- Existing private read-only failure/status captures; absence of a capture cannot be treated as proof of an unused operation.

## Input Validation Checklist

- [ ] Coordinator confirms original executor terminated and production source writer paused before recovery ownership; one writer/executor, release notification assigned.
- [ ] Original e prepared/approval/consumed/failure/ledger/proposal bytes pinned; no old apply rerun, marker reset or new program ledger.
- [ ] Every paid slot is absent/unstarted across original markers and all linked journals; no stop/update/restart/old-drained or ambiguous dispatch evidence exists.
- [ ] Live ingress is DENY, old image/Table/min0/max1/config/secret/account state agrees with e except the authorized fence; quiet two-account state is unchanged.
- [ ] New recovery hashes, source/image compatibility, cold-start branch and exact mutations independently approved before mutation or paid dispatch.
