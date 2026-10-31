# Watchdog Implementation Outputs

## Mandatory Outputs

| Output | Description | Format |
| --- | --- | --- |
| Operator gateway | Standalone package under `scripts/quality/ingress_watchdog/` with signed protocol, durable ledger adapter, lease state machine, TLS transport, probes and redacted evidence | Python/operator artifact |
| Supervisor and verifier | Separate process entry points and authenticated receipt contracts; no runner control-plane privileges | Python/operator artifact |
| Fresh G1 harness | New four-case harness and private packet/evidence formats, preserving old user work and history | Python/operator artifact |
| Tests | Unit, subprocess fault-injection and local TLS/SSE integration tests; storage emulator/fake results distinguished from Azure | `tests/` |
| Verification and reviews | Coverage, static checks, independent deep review, documented failures and unresolved gates | `evidence.md` and review records |
| Independent plan review | Findings, dispositions and outstanding design blocker | [plan-review.md](plan-review.md) |
| Future Azure feasibility and G1 packets | Resource what-if, role/route evidence, diagnostic calibration, budget and signed execution scope | Separate private packets; not created by this planning task |

## Optional Outputs
- Optional local benchmark for lease closure and bounded buffering; never represented as a cloud SLO.

## Output Quality Checklist
- [ ] Each implemented artifact and its exact hashes are independently reviewed.
- [ ] Findings and verification evidence distinguish mocks, non-paid Azure tests and paid G1 outcomes.
- [ ] No secret, prompt, model output, resource identifier or raw diagnostic log is published.
