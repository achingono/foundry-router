# Isolated Ingress Watchdog Exit Criteria

## Gate Checklist

- [x] Independent reviewer approves the amended design requirements with no unresolved Critical/Major findings; implementation and empirical validation remain open.
- [ ] The target uses a dedicated internal ACA environment and VNet with no other reachable workloads. Shared-environment deployment is not an allowed alternative.
- [ ] Gateway is the only routable client of the private ACA target; runner and unrelated workloads have no direct route.
- [ ] Gateway public listener is restricted to the approved executor; ACA has no public endpoint and the private gateway-to-ACA path is tested after restart.
- [ ] Gateway has no Azure control-plane write role; no runner credential can change the gateway or extend the lease beyond the approved limit.
- [ ] Runner/supervisor cannot execute commands in the app, read app/provider secrets, mutate infrastructure, or reach the provider directly; an independently operated diagnostic/restart path supplies required evidence without granting those powers to the runner. Effective permissions and bypass attempts are tested.
- [ ] Gateway verifies a detached reviewer signature over the canonical exact packet using a separately provisioned pinned public key; runner cannot forge or alter the approved scope.
- [ ] Proxy uses a fixed target origin and path/method allowlist, authenticates the runner independently of the app API key, validates TLS, preserves SSE, bounds resource use, and never retries.
- [ ] Session IDs are durably consumed with atomic insert-only semantics; restart/replay cannot re-arm a consumed ID. Ledger outage or ambiguous writes fail closed.
- [ ] A signed, immutable absolute deadline survives renewal/restart semantics; renewal never extends it, clock rollback/uncertainty fails closed, and expiry latency is bounded.
- [ ] Four fresh G1 cases cover two deployments × nonstream/stream; their distinct ordered POSTs are durably consumed before forwarding and bound to packet/session/model/stream/output ceiling/body hash. Each next case requires an independently signed prior settlement/continuity receipt; duplicate, altered, out-of-order, or ambiguous requests halt without replay.
- [ ] An independent verifier establishes a fresh sole-writer baseline, then immediately before every case compares process identity, accounts, debit/recovery counters, cycles and zero reservations/inflight to the last accepted state. The slot is consumed before that snapshot; signed evidence is fresh and no remote operation or wait precedes forwarding. Drift/staleness stops the program.
- [ ] Fresh program allocation and per-case reserves are separately approved against aggregate USD 1 / 16-attempt bounds and existing liabilities; old case slots, results, and ledgers are not reused.
- [ ] Effective pinned router configuration proves zero retry and no failover/multiple provider attempts for each case; config/topology drift stops dispatch and injected failure tests confirm the attempt bound.
- [ ] Proxy enforces lease and absolute expiry itself using monotonic and trusted UTC checks; it starts closed after process/host restart and watchdog loss cannot leave it open.
- [ ] Renewal binds a single-use gateway challenge and supervisor timestamp sampled before exact-child liveness verification; expiry is capped at that timestamp plus TTL and the signed deadline, not receipt time. Delayed/replayed messages, uncertain time, and post-expiry renewals fail closed within the approved clock-uncertainty bound.
- [ ] The final expiry/phase/slot check and nonblocking forwarding initiation are serialized; blocked ledger inserts racing expiry or close consume the slot but send no bytes, and already-initiated work remains uncertain.
- [ ] Lease maximum duration, renewal cadence, expiry latency, stream handling, and in-flight ambiguity are reviewed and measured.
- [ ] Fault injection covers runner SIGTERM/SIGKILL, supervisor failure with runner alive, runner failure with supervisor alive, host loss, gateway restart, replay, stale/invalid lease, network partition, and Azure control-plane outage.
- [ ] Lease expiry blocks new forwarding and terminates active proxied streams within the approved bound; dispatched provider calls remain non-replayable liabilities.
- [ ] Final DENY is verified by distinct one-use ACA-origin 403 probes before and after the single approved restart, sourced from the gateway's private VNet route and each corroborated with fresh exact ARM ingress config. Normal forwarding never reopens; proxy-generated errors and executor network failures do not count.
- [ ] ACA HTTP diagnostic logs are enabled and available; the exact ingress-denial `ResponseCodeDetails` is calibrated against an app-generated 403 on a non-paid disposable app, with request-ID correlation, zero upstream attempts, and no matching app request. A status/body fingerprint alone is insufficient.
- [ ] Gateway outage/uncertain deny is recorded as blocked, never as G1 pass. No automatic app restart or balance mutation occurs.
- [ ] Exact new infrastructure and G1 packets are independently reviewed and approved separately before deployment or paid inference.
- [ ] The mandatory new dedicated environment/test app retires the old G1 case-3 slot and packet; a new four-case budget and exact packet are approved before any paid call.

## Approval Table

| Role | Name | Status | Notes |
|---|---|---|---|
| Owner | Coordinator | Drafted | Design only; no implementation or Azure mutation |
| Reviewer | Independent session | Design-only approved | Eight Majors addressed as requirements; Azure bypass/failure assumptions remain unverified |
| Approver | Operator | Stages approved in principle | User approved all stages; exact infrastructure and execution packets and their independent reviews remain required |
