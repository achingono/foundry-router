# Harness implementation and deployment completion

Date: 2026-10-12. Status: **Implemented and staging deployed; roster acceptance
partially passed and halted.** Production remains planned.

Implementation and review fixes are committed as `e34b506`, `2e18d6f` and
`d5d808a`. This follow-up finishes verification and evidence; it adds no runtime
behavior or infrastructure. Existing plan and implementation reviews remain
linked from the [plan hub](index.md).

## Measured verification

| Check | Result |
| --- | --- |
| Focused harness tests | 69 passed; 81.01% harness coverage |
| Full unit/integration suite excluding Docker/Azurite | 2,505 passed, 3 skipped, 19 deselected; 89.47% runtime coverage |
| Azurite integration suite | 15 passed |
| Ruff lint / format | Passed; 919 files already formatted at initial check |
| Mypy | Passed; 72 source files |
| Docker | Local build passed; repository Docker build-and-health test also passed (1 test); no image pushed or deployed in follow-up |
| SonarQube | Not applicable: conditional scan script absent |
| Contextual deep review | Fresh independent reviewer applied the repository prompt; no new blocking implementation finding; financial/cause evidence correction required and applied |

Independent follow-up accepted the corrected completion/evidence record, closing
the Major financial/cause finding. Its two wording suggestions (staging router
versus harness deployment, and format-check wording) were addressed. No Critical
or Major finding remains in this scoped review. Relative documentation targets
were checked across all 24 plan/canonical files; none were missing.
The retained manifest and all three result records also passed the current
harness validators in a read-only check.

The sandbox full-suite run could not use loopback listeners and was interrupted.
Its complete replacement ran with loopback access and passed. Initial sandbox
Azurite checks skipped; the replacement executed all 15. Development environment:
Python 3.14.7; Docker build uses Python 3.12. Existing deprecation warnings remain.
Logs under `/private/tmp/harness-*` are local-only.

## Read-only deployed-state follow-up

Azure reported provisioning `Succeeded`, ready revision
`foundry-router-staging--0000002`, the recorded `grimsugar` image tag and maximum
one replica. Public liveness returned `alive`; readiness returned `ready: true`
with every reported check true. Admin reported eight pools, global reserves
USD 10 / 5%, `or-shared` override USD 0.05 / 5%, and inherited `zen-staging`
USD 10 / 5%. Both groups had zero active reservations and zero reserved inflight.
This establishes current quietness, not failed-case historical debit or
uninterrupted memory continuity. The current OR estimate of 4.82 cannot
reconstruct historical settlement. A tag read does not attest the running digest.

The existing local staging admin key was used only in memory; no secret values
were displayed. Key Vault denied an attempted read; no grant was added. A first
admin request used the client header and received 401; the corrected
`x-admin-key` read passed. No inference, vault write, restart, rollout, ledger
reset or production change occurred in this follow-up.

## Remaining acceptance gates

Three slots are consumed: Luna and Haiku passed, DeepSeek returned 502, and
MiMo/Spark were not attempted. The [corrected execution evidence](evidence-roster-2026-10-12.md)
labels the two passing local debits as a subtotal; failed-case debit and cause
remain unverified. Current quietness does not upgrade the failed case to a pass.
Ledgers, identities and results remain unchanged.

Further inference requires a separately reviewed bounded amendment and new
identity. Full roster acceptance, production enforcement/stream qualification,
production seeds/release/maintenance approval and Table cut-over remain open.
Implementation and staging deployment are complete; 5/5 live acceptance and
production readiness are not established.
