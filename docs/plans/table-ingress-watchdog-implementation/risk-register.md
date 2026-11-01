# Watchdog Implementation Risk Register

| ID | Risk | Consequence | Required mitigation | Status |
|---|---|---|---|---|
| R1 | Python TLS/HTTP transport cannot serialize first write and close or terminate idle streams | Late forwarding after expiry | Prove actual nonblocking initiation and cancellation with real TLS, queued-byte and interleaving tests; stop for independently reviewed alternative if infeasible | Open |
| R2 | Time source or uncertainty cannot be authenticated/measured | Delayed heartbeat extends lease | Authenticated time, conservative expiry and `CLOCK_BOOTTIME`; unknown/stale clock closes; real-host fault tests | Open feasibility |
| R3 | WORM policy, SDK retries or failover differs from assumptions | Duplicate authorization | Locked container, explicit conditional create, primary only, no SDK retry, uncertain acknowledgment closes; actual Azure negative tests | Open feasibility |
| R4 | Runner gains control-plane/secret/provider access | Gateway bypass | Separate operator/verifier, denied effective permissions and egress tests; privileged operator remains trusted | Open feasibility |
| R5 | Snapshot or signed receipt is stale or financial state drifts | Paid case against wrong account state | Consume slot first, independent sole-writer snapshot, bounded signed receipt and local immediate gate; stop on drift | Planned |
| R6 | Router retries/fails over despite gateway one-shot | More provider attempts than budgeted | Verify zero retries and one eligible backend per model pool; instrument 429/5xx/transport fault tests | Open feasibility |
| R7 | ACA log semantics or completeness cannot establish ingress denial | False G1 pass | Disposable calibrated denial/app-403 comparison, per-probe correlation and ARM corroboration; ambiguity blocks | Open feasibility |
| R8 | Dedicated environment cannot provide isolated route or operator diagnostic access | Direct bypass or unverifiable financial state | Verify actual route, DNS, RBAC and evidence path before live use; no shared fallback | Open feasibility |
| R9 | Fresh four-case budget exceeds remaining program bounds | Unauthorized spending or allocation duplication | Account for old liabilities/attempts, require exact fresh packet and separate amendment if needed | Open approval |
| R10 | Gateway/proxy restart, WORM retention or failed cleanup makes a session unrecoverable | Blocked acceptance or retained resources | Fail closed, never replay; document locked retention and require separate reviewed recovery/cleanup | Open |
| R11 | A hung runner is still live | Lease remains open until absolute deadline | Treat TTL as a liveness-loss bound only; signed hard deadline and resource limits are mandatory | Design limitation |
| R12 | Receipt delivery/independent diagnostic sampling takes longer than freshness bound | False refusal or expired slot | Measure timing without paid calls; never extend a stale receipt or move a remote wait after verification | Open feasibility |
| R13 | Whole gateway host is suspended or lost | No process can terminate sockets within TTL; already-buffered bytes or provider work may continue | Explicitly exclude finite closure during total host suspension/loss; make the session terminal, check trusted/boot time and close inherited sockets before accepting traffic on resume. Require a separately reviewed independent enforcer if this ordering cannot be proven | **Guarantee narrowed; resume proof open** |
| R14 | Runner shares OS privileges or process access with supervisor | Runner steals heartbeat capability and extends lease | Distinct UIDs, inaccessible key mounts, privilege drop and denied ptrace/FD/memory/token tests | Planned; Linux proof open |
| R15 | External Table writer, background maintenance or cycle rollover changes state after snapshot | Receipt no longer reflects admission state | Prove enforced sole-writer/quiescence/cycle exclusion through forwarding; otherwise block for design amendment | Open feasibility |
| R16 | Runner forges terminal usage or multiple hosts allocate the same program budget | Invalid settlement or overspend | Gateway signs HTTP 200/completion/usage/EOF witness; one session-bound allocation and deterministic allocation-scoped slot markers; budget WORM/hold covers financial lifetime; inventory old liabilities | Open feasibility |

## Decisions requiring exact packet evidence

- Region, VNet/subnet address space, VM size, static endpoint, DNS, Blob/diagnostic resources, cost and retention.
- Target clock source and observed uncertainty; candidate NTS and 2-second combined bound must be demonstrably available.
- Independent operator diagnostic mechanism and effective Azure permissions; no assumption that an Azure role can restrict arbitrary exec to a safe command.
- Exact two physical test deployments, singleton model pools, prices, program liabilities, signer custody and final probe evidence.
