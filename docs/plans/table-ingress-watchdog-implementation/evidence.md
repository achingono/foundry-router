# Watchdog Implementation Evidence

## Evidence Log

| Item | Reference | Notes |
| --- | --- | --- |
| Design review | [Prior design review](../table-ingress-watchdog-20261030/design-review.md) | Design-only approval; implementation and empirical gates remain open |
| Operator stage approval | [Prior evidence](../table-ingress-watchdog-20261030/evidence.md) | User approved stages in principle; no exact resource or paid-execution packet approved |
| Repository inspection | [Current forwarding](../../../src/foundry_router/forwarding/__init__.py), [routing](../../../src/foundry_router/routing/__init__.py) | Forwarding clamps attempts to at least one; routing separately handles retryable failures. Zero retry settings alone do not prove no backend failover |
| Official Azure references | [Blob immutability](https://learn.microsoft.com/azure/storage/blobs/immutable-storage-overview), [ACA HTTP logs](https://learn.microsoft.com/azure/container-apps/log-monitoring) | Locked container WORM and diagnostic fields are documented; target policy, deny fingerprint and log completeness remain unverified |
| Implementation plan review | Independent session | Rejected initial candidate: nine Majors covering credential isolation, quiescence, independent response evidence, WORM retention, diagnostic phase, DENY/restart ordering, Table/four-case matrix, aggregate budget/input bounds, and full-host suspension |
| First plan re-review | Same independent session | Three further Majors: program-wide slot consumption, budget-record financial retention, and explicit HTTP 200/complete/usage/EOF witness requirements |
| Final plan re-review | [Plan review](plan-review.md) | Conditionally approved: no remaining Critical/Major plan findings. Resume-before-accept ordering remains a hard live-use gate |
| Suspension guarantee amendment review | Independent code-review agent, current session | Passed: bounded socket closure is explicitly limited to a running host; total suspension/loss is terminal, and resume ordering must be proven before live use |
| Implementation authorization | User instruction | User approved proceeding with implementation; scope is local-only until separately reviewed Azure and G1 packets |
| Local implementation | `scripts/quality/ingress_watchdog/` | Canonical protocol/signing, clock, create-only ledger, fail-closed state, bounded HTTP/TLS helpers and response inspector are implemented locally. Proxy/control/supervisor/verifier/G1 process wiring and Linux privilege-boundary tests remain outstanding |
| Independent implementation review | Current unstaged diff | Found that a clock error in `close_for_deny` could escape without terminal closure; moved sampling under fail-closed handling and added a regression test |
| Deep implementation review | Independent code-review agent, current session | No significant actionable issues found in the reviewed local primitives; this does not review or validate the still-unimplemented process wiring |
| Focused verification | `tests/unit/test_ingress_watchdog_protocol.py` | 33 focused tests passed; package coverage 85.65%; focused Ruff and Mypy passed. This is not end-to-end, Linux, Azure or provider evidence |
| Repository verification | Local test/tool runs | Full suite: 3,193 passed and 21 skipped. The Docker-build test failed once from truncated package-index JSON, then passed on retry and in the confirming full-suite run. Repository Ruff, format check and Mypy passed; Docker build passed in the full suite |
| Azure and paid G1 | None | No Azure mutations, provider requests, exact packet approval or production cut-over occurred |
| Documentation and diff checks | Plan files and worktree | Documentation updated for partial status; relative links in all nine watchdog plan documents and `git diff --check` passed |
| Review remediation | [Local remediation](../table-watchdog-review-remediation-20261101/evidence.md) | The eight earlier review findings and independent follow-up findings were addressed in local primitives; process wiring, Azure behavior and live G1 remain unverified |
