# Isolated Table Acceptance Ingress Watchdog

**Status: Conditional design target; not implemented or deployed.** Independent
design re-review approved the amended requirements after eight Major findings
were addressed. The operator has approved all stages in principle, including
implementation, Azure validation, and execution. Controls remain unimplemented
and empirically unverified; exact infrastructure and execution packets and their
independent reviews remain required. The old case-3 slot is not transferable.

## Decision

Do not treat a runner `finally` block, shell trap, Azure Function timer, scheduled
Container Apps Job, or periodic ARM patch as a fail-closed watchdog. They can be
skipped, delayed, or unable to reach the Azure control plane. A timer that eventually
PATCHes ingress gives only a best-effort recovery path.

Use an **independent, default-deny forwarding gateway with a short-lived lease,
durable one-use records, and an absolute deadline**. A new dedicated private
Container Apps environment is mandatory for the test target:

1. The existing G1 app is in a shared ACA environment and is not an eligible
   watchdog target. Use a **new dedicated internal ACA environment** containing
   only a fresh isolated test app, attached to a VNet with no peering, VPN, or
   other workloads that can reach it. The environment has no public inbound
   endpoint. A shared environment is not an alternative, even if a bypass test
   appears to pass. The old app cannot simply be moved; a new app/topology needs
   a new exact G1 packet and fresh budget approval. The existing case-3 slot and
   historical result chain are not transferable.
2. The gateway runs in a separate failure domain from the acceptance runner, on a
   dedicated small VM with a public listener restricted to the approved executor
   and a private VNet route to the test app's internal environment endpoint. The
   VNet has no other connected clients. The runner cannot route directly to the
   private environment; its only app route is through the gateway.
3. The gateway has a reverse-proxy listener and a separate lease/watchdog service.
   The runner host cannot stop, reconfigure, or renew the gateway service except
   through its narrow lease API.
4. Before forwarding, the gateway durably consumes a unique, packet-bound session
   ID using an atomic create-only blob in a dedicated locked-WORM container. It binds the
   packet hash and immutable absolute `not_after` deadline. A duplicate arm/replay
   is refused even after a gateway restart. Ledger outage or ambiguous insert
   acknowledgement leaves forwarding closed.
5. A fail-stop supervisor owns renewal and launches/waits for the actual runner
   process. It stops renewing as soon as that child exits; the child has no lease
   renewal secret. Supervisor failure also stops renewal. The gateway proxy
   independently enforces expiry.
6. The supervisor renews a short lease only while its runner child is alive, but
   renewal cannot extend the packet's absolute deadline. The proxy checks lease,
    deadline, request scope, and per-case one-shot dispatch state on every request. On
   expiry it blocks new requests and terminates active proxied streams.
7. On runner death, heartbeat loss, invalid/replayed lease, ledger/control-service
   failure, clock anomaly, or gateway restart, forwarding closes by default. Active
   lease state is never restored after restart; consumed session IDs remain
   durably fenced. The watchdog does not restart the ACA app, retry inference,
   alter credit storage, or change ACA ingress.
8. The private ACA origin is not reachable from the executor or any other workload;
   a failed gateway therefore makes the app unreachable rather than opening a
    direct route. A dedicated internal environment/VNet is mandatory; a shared
    environment is not an approved fallback. Privileged control-plane operators
    remain trusted and are not claimed to be technically incapable of changing it.

This design is fail-closed for **request forwarding after bounded lease expiry**,
not an instantaneous or universal guarantee. A proxy call already dispatched to the
router/provider may continue or settle ambiguously if the runner dies. Preserve the
slot's full liability and never replay it. Azure control-plane and network failures
can also prevent live verification; they must block acceptance, not be described as
a successful deny.

## Proposed isolated topology

```text
Acceptance runner --mTLS/lease--> Gateway VM (public listener restricted to runner)
                                     | default-deny; lease TTL
                                     | private VNet route; only client
                                     v
                     Dedicated internal ACA environment
                     (one test app; no public ingress)
                                     |
                                     v
                              Azure model provider
```

The runner sends only fixed, reviewed routes and methods to one immutable ACA
origin. The gateway does not resolve a caller-supplied host, follow redirects, or
proxy arbitrary URLs. It enforces a strict packet-specific request-body byte cap
and holds the small approved case body in bounded memory until its hash is bound
into the durable one-shot record; it then forwards that body once. It does not
buffer SSE responses. The app's existing client/admin authentication remains
required.
Sensitive payloads, headers, tokens, credentials, and output are never logged.

The lease endpoint is authenticated independently from the app API key (prefer
mutual TLS with a short-lived client certificate or an equivalent packet-bound
capability). Before arming, the gateway validates a detached digital signature
from the independent exact-packet reviewer over a canonical packet digest and
scope. The reviewer's private signing key is not available to the runner; the
gateway holds only a pinned public verification key and signer/key ID policy.
The signed packet binds a unique session ID, origin, methods/routes, the four
ordered paid cases and their distinct IDs and body hashes, resource ceilings,
immutable absolute deadline, and final-probe scope. The gateway rejects unsigned, expired, malformed, or
previously consumed sessions. It cannot accept a runner-provided approval boolean
as authorization.

The lease endpoint accepts only the signed G1 packet/session identifier, target
origin, fixed route set, and bounded expiry. It cannot change the target, slot,
budget, route policy, ACA configuration, or Azure resources. Runner credentials
cannot administer the VM or acquire Azure control-plane credentials through the
gateway.

The gateway authenticates each runner request using the packet-bound client
identity; possession of the router API key alone never authorizes forwarding. A
reviewed method/path allowlist admits only required read-only readiness/admin
probes and the four ordered Responses POSTs. Before forwarding each POST, the
gateway atomically consumes its unique dispatch ID, bound to the session, case
index, approved model/stream/output ceiling, and exact request-body hash. The
insert occurs before any upstream bytes are sent. Duplicate, altered, out-of-order,
unapproved, or ambiguous attempts are refused. No gateway retry is allowed. A
one-shot record is never reset or deleted to recover an uncertain dispatch.

## Fresh G1 protocol and provider attempts

The new app requires a **fresh four-case G1**, not the old remaining slot: two
approved Azure deployments, each nonstream and stream, with a separately reviewed
packet, all four body hashes, per-case reserves, and a fresh program allocation.
The reviewer must reconcile already-consumed program liability and attempts with
the applicable USD 1 / 16-attempt aggregate limit; no new allocation or increase
is implied. If the four cases cannot fit, stop until a separately authorized
budget amendment. Leave old ledgers, receipts, and liabilities untouched; do not
use their results to satisfy the fresh four-case chain.

For each case require HTTP 200, terminal completion, usage and clean streaming EOF
where applicable, the exact configured-price estimated debit, expected counter and
account deltas, and zero reservations/inflight. Before the next case, an independent
financial verifier must authenticate a one-use advancement receipt binding the
session, case index, consumed dispatch, previous and current account snapshots,
usage and settlement evidence, and effective configuration. The gateway accepts
the next ordered slot only after verifying that receipt against a separately
provisioned verifier key; the runner cannot sign it. An ambiguous dispatch,
missing/invalid receipt, financial drift, or failed case stops the entire program:
no retry, later case, refund, or replay. Estimates remain local, not Azure balances.

Before case one, the independent verifier establishes a fresh ready, sole-writer
baseline with process identity, canonical accounts, debit/recovery counters,
cycles, and zero reservations/inflight. Immediately before **every** dispatch,
including case one, it takes a fresh snapshot and compares process identity,
accounts, counters, cycles, and zero reservations/inflight to the last accepted
state. Unexpected active/draining writers, background mutations, configuration
drift, or any mismatch stop before forwarding. The verifier signs a short-lived,
one-use pre-dispatch receipt binding that exact snapshot, slot and session. The
gateway must consume the slot's durable dispatch record before this final snapshot;
it then locally verifies the receipt and immediately initiates forwarding under
the lease/phase ordering below, without another remote operation or wait. Receipt
delivery is bounded by a reviewed freshness limit; stale or ambiguous evidence
consumes the slot and halts. The separately reviewed protocol must demonstrate the
sole-writer and no-intervening-mutation boundary; if it cannot, G1 is blocked.

One gateway POST is not necessarily one provider attempt. Pin the current release,
pool and effective retry/failover configuration, including `FOUNDRY_RETRY_ATTEMPTS=0`,
and prove before each dispatch that the selected route cannot make more than one
provider attempt, including failover. Recheck bound revision, effective settings,
and topology immediately before dispatch; configuration mutation is excluded while
the session is armed. If zero retries and no failover cannot be independently
verified or fault-tested, stop; do not infer it from the gateway's no-retry policy.
Retain the full case liability for uncertain post-dispatch outcomes.

The replay fence is a dedicated Blob container with a **locked time-based
immutability policy**. Each consumed session, paid dispatch, and one-way close
transition is a distinct block blob with a deterministic unique name. Create with
`If-None-Match: *`; only an explicit successful create permits the operation to
continue. A conflict means already consumed; a timeout/lost acknowledgement means
uncertain and therefore closed, with no retry. A read may confirm a record for
forensics, but must never turn an ambiguous create into permission to forward.

The gateway managed identity has a container-scoped Blob data role and no
ARM/control-plane rights. Because the built-in Blob Data Contributor role may
include delete actions, safety relies on a **locked** container-level WORM policy
enforced by Storage, not on the role name. A separate deployment identity creates
the container, locks the policy, and grants the role. Verify effective role
actions and explicit denied delete/overwrite/container-delete attempts before
use. A resource lock and separate operator identity protect the storage resource
from ordinary lifecycle operations. Privileged subscription/storage
administrators remain inside the trusted control-plane boundary; this design does
not claim protection against a malicious Owner.

Retention exceeds the signed packet's maximum validity and replay/forensics
window. Deletion after retention expiry cannot make an old signed packet valid
because the signature's absolute deadline has expired. If container policy,
record creation, role scope, or resource ownership cannot be verified, the
gateway stays closed. No mutable Table row is used as the sole replay fence.

The gateway has no Azure resource-write identity. A separate trusted operator
identity creates the dedicated private environment/test app and applies the
separately approved final DENY and single restart. The runner and supervisor have
no ARM write, container-exec/command, VM administration, app secret-list, Key
Vault secret-read, role-assignment, or provider-credential access. Restrict their
network egress to the gateway and explicitly approved non-provider dependencies;
they cannot call the app or provider through another network path. App client and
admin credentials do not confer provider credentials or cloud administration.
The existing G1 runner's exec and secret-resolution paths are **not compatible**
with this boundary and must not be reused unchanged.

An independently operated, narrowly scoped diagnostic path must provide the
process, topology, effective configuration, account and readiness evidence needed
by G1 without giving the runner arbitrary exec, secrets, or provider access.
Use separately authorized operator-mediated evidence and read-only gateway routes;
do not assume a suitably restricted Azure permission exists. The trusted operator
must not issue inference or expose credentials, and its actions are independently
audited. Before use, test effective runner/supervisor permissions and denied exec,
secret access, direct app/provider egress, and alternate identity/token paths.
If this separation or the required evidence cannot be demonstrated, the design is
blocked. A watchdog expiry is not evidence of ACA DENY, restart, or persistence.

## Lease and watchdog behavior

Candidate timing for test-only evaluation: renew every 3 seconds, expire after 15
seconds without a valid renewal, and set a signed immutable absolute deadline no
later than the existing 30-minute G1 window. These are design values, not verified
Azure or production SLOs. Reviewers must approve timing based on measured latency
and streaming behavior. Renewal can shorten the remaining window, never extend the
absolute deadline.

- Use a monotonic clock for heartbeat age and process-lifetime expiry, plus the
  immutable UTC `not_after` for cross-process validity. If system time moves
  backward beyond tolerance, trusted time is unavailable, or checks disagree,
  close forwarding. Never calculate a later deadline after restart.
- The trusted UTC clock source and rollback tolerance must be explicitly selected
  and fault-tested on both supervisor and gateway, including clock skew and host
  suspend/resume. A restarted gateway never restores an active lease; if time
  cannot be trusted, it refuses both arm and forwarding.
- Keep active lease state only in memory, but keep consumed session and paid
  dispatch IDs in the durable insert-only ledger. Process start/restart starts
  closed. A still-valid old arm credential cannot re-arm a consumed session.
- The proxy's request path enforces expiry itself; it must not rely solely on a
  watchdog thread, runner `finally`, shell trap, schedule, or health probe. Its
  own expiry mechanism also cancels idle active streams without another request.
- Host firewall/network namespaces constrain ACA-bound egress to the proxy service;
  runner credentials provide no shell, service-control, raw-socket, or VM
  administration access. Validate this boundary with direct-origin bypass tests.
- A one-shot local supervisor launches and waits for the actual runner process.
  Only this supervisor holds the heartbeat-renewal capability; the runner child
  has no renewal credential, and credentials are not inherited by helper/CLI
  subprocesses. The supervisor renews only while the exact child PID plus process
  start identity remains alive and before the signed deadline. It checks child
  liveness synchronously, not through an independent background thread.
- Every renewal binds a fresh gateway challenge and session ID to a supervisor
  timestamp sampled immediately **before** its synchronous check that the exact
  child is alive. Sign/authenticate the timestamp and challenge; reject reused
  challenges, future/out-of-tolerance timestamps, uncertain clocks, and renewals
  processed after the current lease has expired or closed. The gateway caps the
  renewed expiry at the authenticated check timestamp plus TTL and the signed
  absolute deadline, never at receipt time plus TTL. The approved bound includes
  the measured maximum clock skew/uncertainty; if that bound cannot be established,
  refuse renewal. Delayed packets cannot gain a fresh TTL on arrival.
- If the runner child exits, the supervisor immediately asks the gateway to close
  the lease and stops renewing. If the supervisor dies, hangs, loses child
  identity, or loses network, renewal stops; the gateway proxy's own lease expiry
  closes forwarding within TTL plus the approved clock uncertainty from the last
  qualifying liveness check. The proxy independently denies when the lease is
  absent or expired, even if the separate watchdog process is stopped.
- A hung but still-live runner can continue to be renewed: the short lease bounds
  loss of verified liveness, not lack of progress. The signed absolute deadline is
  the final bound for that case; a progress watchdog is not claimed.
- Fault injection must SIGKILL the runner child while leaving the supervisor
  running, kill the supervisor while leaving the runner child, and kill both.
  In every case, no actor other than the still-live supervisor may renew, and
  the fixed absolute deadline remains the final upper bound.
- On expiry, atomically disable new upstream requests and terminate open
  downstream/upstream proxy streams. Record only packet/session ID, timestamps,
  state transitions, and request correlation hashes. Any in-flight provider call
  remains financially uncertain until reconciled by the existing G1 process.
- A dispatch's slow durable insert is not permission to send later. Serialize the
  final lease/deadline/phase and expected-slot recheck with initiation of upstream
  forwarding; expiry or `close_for_deny` wins if observed first. Use a nonblocking,
  bounded initiation under that ordering, never hold the phase lock over a ledger
  write or streaming I/O. If the insert succeeds after closure/expiry, consume the
  slot but send no bytes and halt. Once forwarding initiates before closure, treat
  it as dispatched and financially uncertain; cancellation cannot undo provider
  work. Fault-test blocked writes, deadline expiry, and concurrent closure.
- The watchdog emits a sanitized expiry/health event to an independent durable
  sink. Failure to emit an event does not keep forwarding open. Event collection
  is diagnostic only.

## Denial Proof and Origin-Side Probe

The runner's direct request to the app origin cannot verify final DENY: the
runner has no private route to the ACA environment, and a connection failure or
403 from another boundary is not proof ACA denied ingress. A future runner
change must use a gateway-origin probe; never accept an executor-origin 403 or
network failure as proof of the ACA ingress policy.

After the separately approved final-DENY PATCH, the gateway makes two separately
authorized, one-use read-only probes to the pinned ACA origin from its private VNet
route: one before the single approved restart and one after it. Each probe is distinct
from client proxying and cannot reopen or renew the lease. It must observe an
TLS-validated 403 from ACA. Status and response shape alone are not sufficient:
the application could generate the same response. Enable ACA environment HTTP
diagnostic logs before the test and bind the probe's request ID to its ingress
record. Require a 403 record whose `ResponseCodeDetails` value has been
independently calibrated to mean an ingress policy rejection, whose
`UpstreamRequestAttemptCount` is zero, and for which the app has no matching
request log. `direct_response` or zero upstream attempts alone are not proof.
Calibrate the exact observed field values using a non-paid disposable app and
known ingress-policy allow/deny before relying on them. If ACA diagnostics are
missing, delayed beyond the approved verification window, or ambiguous, the
result is blocked; do not infer ingress attribution. A proxy-generated 403,
connection refusal, DNS/TLS error, timeout, or gateway 502 does not count.
Corroborate each probe with a fresh ARM GET showing the exact private-ingress
configuration, performed by the independent operator. The gateway signs a redacted
origin-probe attestation bound to packet/session, phase, origin, observed upstream
status, request ID, calibrated diagnostic evidence, and evidence hashes; the
result binds each attestation to its corresponding separate ARM GET hash. The
gateway does not claim to observe or sign ARM state it cannot read.
Stop if the 403 cannot be attributed to ACA ingress.

Before the ARM final-DENY PATCH, the runner sends a packet-bound one-way
`close_for_deny` command. The gateway durably consumes that phase transition and
closes all normal proxy forwarding; it cannot reopen the lease or dispatch. After
the operator applies DENY, the gateway accepts only the two separately scoped,
authenticated, GET-only origin probes for `/health/ready` and the pinned ACA
origin. Each phase has a distinct durable one-use marker and approved deadline;
the post-restart probe requires verified completion of the one approved restart.
No probe may renew or reopen forwarding, and uncertain marker/probe outcomes block
acceptance without replay. Gateway restart remains closed and blocks continuation;
it does not restore diagnostic authority. Capture a successful pre-deny probe
from the same gateway and verify it returned 200. After DENY, require a
TLS-validated upstream response with status 403 and the calibrated ACA ingress
diagnostic evidence described above, not an app/proxy-generated response. The
runner's direct network failure or 403 is never sufficient. Readiness/admin routes
cannot call Responses, embeddings, alternate paths, or other billable operations.
Each paid POST record is consumed before forwarding, including when its response
later becomes ambiguous. Restart is permitted only after all four cases, pre-restart
DENY proof and quiet drain; the final result also requires the independent
post-restart DENY proof, changed process identity, readiness and unchanged accounts.

## Why an ARM-only watchdog is insufficient

Azure Container Apps supports public ingress and ingress IP restrictions, but
those restrictions are a resource configuration, not a local lease with an
automatic expiry. A separate Function/Job could notice a missing heartbeat and
attempt a management-plane update, but schedules, execution delays, provider
availability, and ARM reachability make that an eventual remediation mechanism,
not a hard data-plane gate. It also leaves a window where the current allow rule
remains active. Do not use that as the sole mitigation for the reviewer finding.

Container Apps Jobs offer manual, scheduled, and event-driven triggers; a schedule
is not an inline enforcement point for each inbound request. A gateway whose route
is closed locally at lease expiry is the enforcement point. Azure ingress
restrictions remain defense in depth; the dedicated internal environment/VNet
and verified route isolation are the primary network boundary.

## Required assumptions and unresolved feasibility

- The gateway public IP is for runner-to-gateway traffic only. Restrict its
  listener to the approved executor, pin its DNS/certificate, and validate the
  endpoint after restart. Do not treat this public address as the ACA origin
  trust boundary.
- Verify the private gateway VM route reaches the internal ACA environment and
  that no runner, peered VNet, VPN, or other ACA app can reach the origin directly.
  Bind VNet/subnet/route/NSG/private-DNS state and the trusted operator's actual
  control-plane permissions in evidence.
- Provision the independent reviewer's signing public key and key ID through a
  separate reviewed deployment path. Test forged approval, wrong key ID, altered
  packet, expired signature, and signature replay. No active runner-supplied
  approval artifact may bypass signature verification.
- Verify the isolated test app can reach the gateway-pinned origin without
  redirect, DNS rebinding, certificate-validation, WebSocket/SSE, or client-IP
  surprises. The gateway must use fixed origin binding and TLS verification.
- Verify the runner cannot bypass the proxy from the gateway host, any alternate
  FQDN, private endpoint, peered network, or runner-accessible management path.
  The present shared ACA environment is ineligible regardless of test results.
  Test the new dedicated environment and all relevant identities and routes;
  do not rely on public IP restrictions alone for isolation.
- Measure stream lifetime, proxy idle timeouts, max request/response sizes, and
  cancellation behavior. Preserve SSE framing; never retry after forwarding starts.
- Verify ACA HTTP diagnostic settings are enabled and queryable for the target
  environment. In a non-paid disposable app, record the exact HTTP-log evidence
  for a known ingress-policy denial and for an app-generated 403. If those cases
  cannot be distinguished reliably by request ID, response-code details,
  upstream-attempt count, and app logs, the final-DENY proof is infeasible and
  the design remains blocked.
- Confirm VM availability, static-IP retention, OS patching, monitoring, budget,
  and ownership. Gateway outage is closed for traffic but blocks acceptance.
- Decide whether a small dedicated VM and its ongoing maintenance/cost are
  acceptable. If not, a managed gateway with an equivalent locally enforced
  expiring lease may be evaluated, but it must prove no direct ACA bypass and
  default-deny on restart. Do not substitute an unverified periodic ARM patch.

## Acceptance sequence after separate approvals

1. Build and independently review the gateway, four-case protocol, operator and
   verifier boundaries, tests, and exact network policy. Threat-model runner and
   gateway failure, delayed/replayed renewals, clock uncertainty, ledger outage,
   dispatch/closure races, retries/failover, privileged bypass, and uncertain work.
2. Deploy only the gateway, dedicated internal ACA environment, isolated VNet,
   and required storage ledger under a reviewed finite what-if. Verify the
   gateway has no ACA ARM-write role and no other workload can route to the app.
3. Keep the ACA origin private with no public endpoint. Verify the runner cannot
   reach the origin directly while the gateway can reach it over the private
   route. The new test app requires a new four-case G1 packet and budget.
4. Fault-inject runner SIGTERM, SIGKILL, host disconnect, lost heartbeat, gateway
   watchdog crash, proxy restart, replay of the same arm credential after restart,
   invalid/stale lease, delayed renewal after child death, clock rollback/suspend,
   ledger outage, blocked inserts racing expiry/close, and Azure control-plane
   outage. After expiry, forwarding must stop within the approved bound.
5. Verify each of the four approved POSTs is durably consumed once before the
   fresh pre-dispatch financial snapshot and forwarding, and only after prior
   settlement approval. Inject financial/process/sole-writer drift and stale
   receipts before each case: no paid request may be forwarded. Duplicate, out-of-order,
   changed, oversized, or ambiguous requests must not be forwarded. Fault-test
   the router's zero-retry/no-failover provider-attempt bound and verify denied
   runner exec, secrets, direct provider access, and alternate paid routes.
6. Verify streamed response framing under a valid lease and confirm expiry
   terminates proxy forwarding without retry. Reconcile any request already
   dispatched before termination as uncertain; do not make a second paid attempt.
7. After final-DENY PATCH, verify separately scoped ACA-generated 403s before and
   after restart from the gateway's private VNet route, with calibrated HTTP
   diagnostics and no matching app request; corroborate each with exact ARM ingress
   configuration. Proxy-local errors and direct executor failures are insufficient.
8. Only after independent design, implementation, infrastructure, and exact-packet
   reviews pass may a new G1 packet bind the gateway image/config, VNet/private
   origin, runner endpoint restriction, durable consumed-session and dispatch
   records, absolute deadline, lease timings, both origin-probe attestations,
   four-case settlement chain, and explicitly approved aggregate budget.

No phase above is authorized by this design review. The previous rejected G1
packet is not reusable after the network topology changes.

## References

- [Azure Container Apps ingress](https://learn.microsoft.com/azure/container-apps/ingress-overview)
- [Azure Container Apps jobs](https://learn.microsoft.com/azure/container-apps/jobs)
- [Azure Static public IP addresses](https://learn.microsoft.com/azure/virtual-network/ip-services/public-ip-addresses)
- [Azure Blob immutable storage](https://learn.microsoft.com/azure/storage/blobs/immutable-storage-overview)
