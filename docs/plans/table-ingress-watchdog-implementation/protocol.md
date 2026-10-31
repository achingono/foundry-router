# Concrete Watchdog Protocol

**Status: Planned, subject to implementation-plan review.** These are candidate
local contracts, not evidence that Azure or the chosen transport supports them.
No endpoint, key, credential, model ID or resource ID is hard-coded.

## Components and trust

| Component | Planned location and authority |
|---|---|
| Proxy | Linux gateway VM; `scripts/quality/ingress_watchdog/proxy.py`; sole owner of upstream sockets, active lease/phase state, expiry timer and one-shot dispatch ordering. |
| Control/watchdog | Separate VM process; `control.py`; authenticated arm/heartbeat/close relay over a restricted Unix-domain socket. It cannot issue upstream requests; proxy closes on control disconnect and independently expires streams. |
| Supervisor | Separate runner-host process; `supervisor.py`; launches/waits for the runner, exclusively owns heartbeat client identity, checks exact child liveness and requests close on exit. It cannot administer the gateway or receive provider credentials. |
| Runner | New four-case client; `g1.py`; client-only identity and app client key; no ARM write, app exec, app secret-list or provider credentials. |
| Verifier/operator | Independent, trusted process and identity; `verifier.py`; obtains read-only operator-mediated diagnostics, checks financial chain and signs one-use receipts. It is not launched or controlled by the runner. The operator separately performs the exact DENY/restart mutations. |
| Ledger | `ledger.py`; locked container-level WORM Blob adapter with conditional create. The VM identity has only required data access; the deployment operator manages policy separately. |

The supervisor and runner use **different Linux UIDs**. A narrowly privileged,
operator-installed supervisor launches its child, drops the child's UID/GID and
supplementary groups irreversibly, closes all nonessential descriptors, clears
credentials and capabilities, and sets `no_new_privs` before exec. Supervisor
keys reside in a supervisor-only mount and are never readable by the runner;
the runner has no sudo, ptrace, `CAP_SYS_PTRACE`, host administrator or alternate
identity-token access. Harden `/proc` and ptrace policy and use a separately
restricted runner network namespace. Test file, process-memory, descriptor,
signal, credential and identity-token access as the runner UID on the actual
Linux configuration. If the OS cannot enforce this boundary, do not arm.

Gateway and runner listeners use TLS 1.2 or later with client-certificate
authentication. The proxy/control processes verify certificate chains and the
packet-bound leaf public-key fingerprints themselves; client-provided identity
headers are never trusted. Use Python 3.12 asyncio TLS streams with an explicitly
declared, bounded `h11` HTTP/1.1 parser, not an ad hoc HTTP parser. Restrict
methods, targets, headers, body sizes and concurrency; reject upgrades,
ambiguous framing, duplicate framing/host headers and query strings. Fixed-origin
TLS verifies hostname and certificate; no caller-selected URL, redirect,
environment proxy, DNS override, or transport retry is permitted. The control
Unix socket uses restrictive ownership/mode and verified peer credentials. If
the selected transport cannot enforce the ordering/cancellation rules below,
**stop and independently amend the plan**; do not replace it with an unverified
reverse-proxy configuration.

## Signed objects and durable names

Use `cryptography` Ed25519 and domain-separated signatures. Define one strict
versioned UTF-8 JSON encoding: sorted ASCII keys, compact separators, ASCII
strings, integers only for times/limits/currency subunits, no duplicate or
unknown fields, no NaN, and an exact byte-for-byte canonical re-encoding check.
Reject noncanonical input, oversized documents, unknown versions, algorithms,
key IDs and invalid signatures before any ledger write. Sign the bytes
`foundry-watchdog/<object-kind>/v1\0` followed by the canonical body. Reviewer,
financial verifier, supervisor and gateway attestation keys have separate roles;
only public verification keys are provisioned to other roles. Runner cannot
sign reviewer, verifier or heartbeat objects.

The signed packet contains: random session ID, packet hash and signer/key ID;
fixed origin hostname/port and approved route/method set; exact gateway and
runner identity fingerprints; VM image/config and private-boundary evidence
hashes; absolute UTC expiry and timing/resource caps; four ordered case IDs,
exact request-body SHA-256, model, stream flag, output ceiling and reserve; and
two distinct pre/post-restart probe scopes. The independently reviewed exact
packet additionally binds fresh four-case budget, prior consumed liabilities,
effective app/configuration/pricing, receipt-verifier keys and zero-retry/single-
backend-pool predicates. IDs are bounded random ASCII; blob object names use
fixed prefixes plus SHA-256 of the canonical session/case/phase ID, never paths
from a request.

The ledger creates distinct deterministic block blobs for `arm`, each `dispatch`,
each verifier `advance`, `close`, and each denial `probe`, using a single
conditional create (`If-None-Match: *`). Only an explicit success authorizes the
next transition. Conflict, timeout, cancellation, unexpected status or lost
acknowledgement is terminal and closed; a subsequent read is forensic only.
Disable SDK operation retries, secondary reads, automatic account failover and
shared-key/default credential fallback. Use the pinned managed identity and
primary endpoint. Check locked container policy, account/endpoint ownership,
role scope and retention before arming; the trusted operator attests the
control-plane properties because the gateway has no ARM read/write authority.
No deletion or reset is allowed. A new session is not a recovery of a consumed
slot or a second allocation.

The signed packet limits validity to at most 30 minutes from arm; the proposed
container retention is **at least eight days**, covering that full interval plus
a seven-day replay/forensics window. The operator attests actual locked-policy
state, retention and primary account before every arm; shorter or unverifiable
retention blocks. Independently test create, conditional collision, denied
overwrite/delete and attempted replay after expiry in a non-paid disposable
account. The exact retained evidence and eventual cleanup are separately reviewed.

## Program-wide financial allocation

Before preparing the four cases, the trusted budget authority freezes every
prior program ledger and stops its executors, then independently inventories all
consumed attempts and full outstanding liabilities. It signs one complete
allocation manifest with the agreed funding-account/cycle/program identity,
prior ledger hashes, aggregate USD 1 / 16-attempt ceiling, all four new slot
reserves and the remaining headroom. No fresh cases can be authorized if the
inventory is incomplete or any prior executor can still dispatch.

Serialize this allocation across hosts with one deterministic conditional WORM
create keyed by the independently agreed funding-account/cycle/program identity,
**not** a new session or caller-chosen ID. The signed allocation binds exactly
one session and four ordered program-wide slot IDs; the gateway rejects any
different session or slot. Before the session dispatch record, atomically consume
a separate deterministic WORM marker keyed by **allocation and slot**, independent
of the session or gateway host. A competing session/host, second create, lost
acknowledgement or conflicting manifest stops; a consumed or ambiguous budget
slot is never retried and retains its full liability. All gateways and verifiers
must validate the same allocation and slot binding. Only the independent budget
authority can sign an allocation; it must also attest that no parallel authority
can issue a second budget identity for the same funding period. A later allocation
or limit increase requires a separately reviewed amendment that preserves the
prior consumed accounting; it is never automatically recovered or reset. Local
locks alone do not establish this global property. Test competing sessions on
different hosts and failures between the budget-slot and dispatch writes.

Budget allocation and budget-slot markers use a **separate** WORM container from
the eight-day session replay records. Its locked retention must cover at least the
funding-cycle end plus the separately approved audit window; a container legal
hold remains in place until every liability and reconciliation is resolved. The
budget authority independently attests policy, hold and role scope before any
allocation. Clearing the hold or changing the budget epoch requires a separately
reviewed closure decision, never an automatic cleanup. If retention, hold or
financial-scope uniqueness cannot be demonstrated, refuse all dispatches. Test
attempted reallocation across expiry, unresolved liabilities and rejected
premature hold clearance. Eight days of session retention alone is insufficient.

The default packet keeps the original 64-input/128-output ceilings. Before any
dispatch the verifier must prove a conservative input-token and price ceiling
for the exact body and selected model, including provider framing/overhead, using
a source-backed verified counting method. Post-response usage alone is not such a
proof. If the provider bound cannot be established, halt; alternatively a
separately reviewed exact-packet amendment may reserve a defensible higher
worst-case liability and change the input limit only if it fits the same approved
aggregate budget. Do not assume bytes equal tokens or claim a token-count API is
free. A case with uncertain outcome keeps its full reserved liability.

## Clock and lease

Candidate policy is 3-second renewal, 15-second TTL, signed maximum 30-minute
session, and a maximum **combined** clock uncertainty of 2 seconds. These are
test-only limits, not observed SLOs. Gateway and supervisor require authenticated
time synchronization with independently measurable uncertainty (candidate:
chrony with authenticated NTS), and Linux `CLOCK_BOOTTIME` for process-local
deadlines so host suspend is included. A root-owned monitor reports source health,
offset and uncertainty; stale status, excessive uncertainty, rollback, suspend
anomaly, missing `CLOCK_BOOTTIME`, or inconsistent clocks immediately closes.
Prove the chosen source/monitor actually provides those properties in the target
environment; if not, block and seek a reviewed amendment rather than silently use
an untrusted wall clock. Unit tests inject fake clock/status providers.

Each renewal uses one fresh gateway nonce and a supervisor-authenticated
timestamp sampled immediately before checking that the original PID **and start
identity** are live and not a zombie. The gateway rejects duplicate nonce,
wrong identity, future/out-of-tolerance timestamp, or renewal at/after existing
expiry. Compute expiry no later than `observed_utc + 15s - combined_uncertainty`
and the signed absolute deadline, converted conservatively to `CLOCK_BOOTTIME`;
never use receipt time plus TTL. Verify behavior with delayed packets and clock
uncertainty in both directions. Initial arm consumes its ledger record but opens
only after a qualifying first heartbeat. Any control disconnect, malformed
authenticated renewal, failed timing check or expiry closes the proxy. A hung
but live runner may renew only until the signed absolute deadline.

## Suspension and independent stream enforcement

`CLOCK_BOOTTIME` detects elapsed suspend time only **after execution resumes**;
it does not close sockets while the entire VM or both processes are suspended.
Likewise, TLS/kernel/network bytes already queued may still be delivered. The
proxy's timer is sufficient only while the proxy can run. If the proxy is
SIGSTOPped while the independent watchdog and OS run, the watchdog must detect
the missed local pulse within the approved bound and terminate the proxy process
and its sockets; if the watchdog dies or is stopped while the proxy runs, the
proxy independently expires and cancels streams. Test both independently with
real TLS sockets, queued bytes and stalled event loops.

**Blocking design decision before implementation:** the original design promises
stream termination within the approved TTL even for host loss/suspend. A single
fully suspended VM cannot establish that promise. An independent design
amendment must either specify and validate a separate failure-domain data-plane
enforcer that can terminate active connections within the bound even while the
gateway VM is suspended, or explicitly narrow the guarantee and its acceptance
criteria to acknowledge buffered/in-flight bytes and no finite close bound during
total host suspension. Until that amendment is independently reviewed, do not
implement or claim the design's host-suspension guarantee. On resume, regardless
of the chosen amendment, recheck boot-time deadline before any new forwarding;
an expired session remains terminally closed and dispatched provider work remains
uncertain. Test proxy SIGSTOP, watchdog SIGSTOP, simultaneous stop, VM suspend,
resume and host loss separately.

## Case transaction and race ordering

Before the baseline, bind the actual test app's effective **Table** state mode,
credit/health table identities and partitions, unique scoped managed identity,
current image and one ready worker with all other revisions inactive/drained.
Require exactly two distinct physical Azure deployments, each represented once
as nonstream and once as stream, and verify mappings are disjoint from production.
The exact packet pins these predicates and their fresh evidence.

The independent verifier must establish and maintain a no-intervening-mutation
boundary through each forwarding initiation, not merely compare a snapshot. The
implementation must prove for the bound release and effective settings that: (a)
the gateway is the only admission path and no request is in flight; (b) the only
Table writer is the isolated app identity, with no external writer/maintenance
actor or competing revision; (c) static reconciliation has no overrides and
all reconciliation, tracked-ownership and reservation-reaper work is quiescent
and cannot mutate the relevant balances under the verified zero-reservation and
zero-pending-ownership conditions; and (d) the entire approved snapshot-to-send
window lies outside any credit-cycle rollover. Verify actual rows, pending
reservations and effective identity/role scope, not only cached readiness. Pin
config and prove no control-plane mutations can occur during the session. Analyze
the existing background loop and prove these predicates with injected concurrent
reaper/reconciliation/rollover/external-writer tests. If the current release
cannot enforce or prove them, block dispatch and obtain a separately reviewed
design amendment for an enforceable fence; do not silently weaken G1 or add an
unreviewed test-only router change.

1. Authenticate the runner, verify the active session, allocation-bound program
   and exact next case,
   boundedly buffer and hash the approved request body. Establish the fixed-origin
   TLS connection before the financial snapshot; send **no upstream HTTP bytes**.
2. Mark the slot pending under the proxy's state lock, release it, conditionally
   consume its allocation-scoped budget-slot marker, then perform the conditional
   session `dispatch` create. Failed or ambiguous writes consume/strand the slot
   and halt. A close/expiry is never blocked by either storage operation.
3. An independently authenticated gateway preparation notice identifies the
   consumed slot to the verifier. After the success acknowledgement, the verifier
   obtains a fresh ready/sole-writer process/config/account snapshot through the
   independent operator path. It compares account membership, balances, debit and
   recovery counters, cycles, process identity and zero reservations/inflight to
   the initial baseline or last accepted result; it signs a short-lived one-use
   receipt binding session, case, dispatch-record hash, full snapshot digest,
   config and observation time. Receipt delivery is part of that one snapshot
   transaction; no further remote operation or wait is allowed after verification.
4. On receipt, locally verify signature, freshness, slot and prior advancement,
   then under the same phase lock recheck lease/deadline/phase and initiate the
   first upstream HTTP write via a bounded nonblocking operation. If expiry/close
   was observed first or receipt is stale, send no bytes and halt. Never hold the
   lock over storage calls or streaming I/O. Once any write is initiated, classify
   the case as dispatched; buffered/in-flight provider work cannot be undone.
5. Stream response bytes without altering SSE boundaries. In the gateway's
   separate bounded inspection path, observe actual upstream HTTP status,
   completion event, numerical terminal usage and clean EOF, then sign a response
   witness bound to session, dispatch record, case and exact response digest.
   Nonstream inspection uses a bounded response buffer; SSE inspection is
   incremental. Never persist/log response text or raw frames. The independent
   verifier checks the gateway's signed witness—not runner-written artifacts—
   and requires **HTTP 200**, completed status, valid bounded numerical usage,
   exactly one valid terminal completion and clean message/stream EOF. Any
   non-200 status (including other 2xx), failed/incomplete/duplicate terminal,
   malformed/over-bound usage or interrupted stream halts the program. It
   compares that witness to its own post-case financial snapshot, exact price/debit
   and zero reservations before signing the one-use advancement receipt. Enforce bounded
   buffers/deadlines and cancel idle active sockets on expiry; never retry/fail
   over. A failed, ambiguous or incomplete case ends the program with its full
   liability; no later case, refund or automatic recovery is permitted.

The exact app has `FOUNDRY_RETRY_ATTEMPTS=0` and each of the two test model pools
has exactly one eligible Azure physical backend with no fallback. Verify effective
image/config and all-revision sole-writer state at baseline and immediately
before each case, and inject 429/5xx/transport errors to count actual backend
attempts in local tests. If the existing configuration cannot express the exact
two one-backend pools without altering supported semantics, stop for a separate
reviewed amendment; a proxy-level no-retry claim is not enough.

The proxy and control emit signed, sanitized health/expiry and irreversible
transition events to a separately operated durable sink with bounded nonblocking
delivery. Failure to emit never keeps the gate open or turns a missing event
into success; operational acceptance requires independent event availability
and completeness evidence. An outbox must contain no credentials, prompts,
raw payloads or model output.

## One-way close and proof

After all four settlements, require a successful pinned-origin TLS-validated
`GET /health/ready` returning HTTP 200 from the same gateway route. A signed,
one-use `close_for_deny` then closes normal forwarding **before** attempting its
durable marker. If marker creation is uncertain, remain closed and refuse
probes/restart. The separately trusted operator consumes a distinct durable
one-use DENY marker before applying the one approved DENY. Lost acknowledgement
or uncertain mutation blocks without a second PATCH.

Only a successful, live-session close can enter a **diagnostic-only** phase.
The normal heartbeat lease is finished and cannot reopen; two separately signed
phase authorizations permit only fixed-origin GETs and have distinct deadlines
within the original signed absolute 30-minute session deadline. Diagnostic
authorization does not depend on renewing the normal 15-second lease. An
unexpected lease expiry before successful close, process restart, control
disconnect, ambiguous close or diagnostic deadline expiry closes all phases and
blocks continuation. No probe path can proxy other routes or paid traffic.

The verifier validates exact ARM state and authorizes the signed, single-use
pre-restart probe. The proxy consumes its phase-specific marker before the GET and
attests TLS-validated upstream **403**, fixed origin and unique request ID. The
independent verifier requires the calibrated ingress-policy
`ResponseCodeDetails`, **zero upstream attempts**, complete app logs with no
matching request, and a fresh exact ARM GET; neither status alone nor proxy errors
count. The gateway does not claim it independently verified those external logs.

After a verified quiet drain and pre-restart DENY proof, the trusted operator
durably consumes a distinct one-shot restart marker bound to the session and
revision **before** making the single restart mutation. A lost acknowledgement,
crash or uncertain outcome is retained and never automatically retried. The
operator independently observes an actual changed process, readiness, sole-worker
topology and unchanged Table accounts, and signs a restart-completion attestation
bound to that marker. Only then can the verifier authorize the distinct one-use
post-restart probe. It must independently meet the same TLS-validated 403,
calibrated details, zero attempts, complete app-log and fresh ARM conditions with
a new request ID. The verifier signs final combined evidence. Probe timeout,
retry ambiguity, missing/delayed/incomplete logs or gateway restart blocks
acceptance. Fault-test crashes before/after every marker and mutation.
