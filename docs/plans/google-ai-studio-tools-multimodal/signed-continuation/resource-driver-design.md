# Resource-driver follow-ups: PDF worker RSS and benchmark client thread-offload attribution

**Planned**, 2026-10-07; independent pre-implementation review cleared with binding
conditions folded in below, plus a second-round amendment round (await-boundary,
thread-offload, equivalence, attribution qualification) also folded in — implementation
may proceed only under all of them. Parent:
[combined-resource-design](combined-resource-design.md) (envelope, caps and accounting
unchanged). Evidence: quote-reconciled and quote-pdf isolated artifacts in this folder.
No cap change, no new capability, no limit increase is proposed.

## Driver A — PDF worker RSS under concurrency

First joint signed-PDF runs (8 callers x 100, two maximum 2-page PDFs per request,
network-disabled Linux 512 MiB / 2 CPUs) record 266,797,056 B (preencoded) and
193,884,160 B (full SDK) incremental parent+children RSS against the 134,217,728 B cap,
with otherwise correct completions, settlement, drain and zero post-dispatch failures.
Quote-heavy runs without media stay closer to the cap (175/112 MB), so per-request PDF
preparation under concurrency is the leading incremental driver **as a hypothesis to be
tested, not an established fact** — that attribution stands only after the separated
measurement below.

Propose, in order, measurement before mechanism:

1. Attribute child RSS separately (parent sampler vs PDF worker peak) across a joint run,
   reusing the existing aggregate sampler; report per-phase peaks (intake, PDF prepare,
   crypto/seal, translate) without changing what is measured. Record parent and child
   RSS at matching timestamps together with child identity (PID/role) and the sampler's
   interval and any sampling gaps: the loop-driven sampler sleeps between samples and can
   miss short-lived peaks, and concurrent requests overlap phases, so unattributed or
   gap-blind peaks must not be assigned to a phase. Per-phase peaks are diagnostic
   only: the sole pass metric remains incremental aggregate parent+children
   (`peak - baseline <= 134,217,728 B`); no phase subset may be quoted as a pass.
2. If preparation dominates, a warm worker or any new bounding/fail-before-read point,
   raised slot/orphan limit, `503`-to-wait conversion, cross-request byte sharing, shared
   snapshot, or change to `PreparedGoogleMedia.validate` identity/digest checks is
   explicitly out of scope under this design and requires its own feature-local design
   plus independent review before code. No runtime edit of any kind until the
   attribution artifact of step 1 is filed. No new slots, no queue, no raised
   `active`, `_SLOTS` or orphan limits. Request isolation and owned snapshots remain.
3. Re-run the identical joint fixtures (preencoded and full SDK, sequential isolated)
   against the same caps; a smaller fixture or reduced concurrency is not an
   acceptable pass — only the reviewed mechanism under the full envelope counts.

## Driver B — benchmark client thread-offload attribution for loop delay

Full-SDK runs record 101–129 ms maximum loop delay against the 50 ms cap while preencoded
runs on the same router code record 39–44 ms. The SDK path adds client-side request
serialization (~1.7 MB wire), mock-provider JSON decode and harness post-response checks
on the same event loop whose delay is being measured. Production clients run in their
own processes, so the shared-loop client cost overstates router loop occupancy — but of
these three, only SDK serialization and post-response checks are eligible to move (see
boundary below); mock-provider decode/assertion of the outbound request stays in the
measured path as separately timed harness overhead, never router work.

Propose a harness-only correction, reviewed before use. Corrected attribution model: the
`httpx.MockTransport` provider handler runs inside the router's awaited backend call, but
what it does with that position is harness work, not router work — it `json.loads`es the
**outbound request** and asserts native replay/signature/media shape, validation that in
production is performed remotely by the provider. It does not model production response
parsing (httpx decoding the provider's response body, a separate smaller cost the mock
path exercises only trivially by constructing a `Response` from an already-parsed
dict). The mock decode/assert section therefore stays in the measured path (its
validation cannot be removed) but must be **timed separately, always on rather than
`--profile`-only, and reported per artifact as harness overhead** — never attributed to
the router. Only stages strictly outside the router's await chain may move off-loop:
synthetic SDK request serialization (before ASGI transport send) and post-response
completion/carrier checks (after the SDK returns a terminal). The router request path
(intake, `PdfPreparer.prepare/inspect`, `SignedWorkLease`/`bounded_signed_work`
including its `asyncio.to_thread(run)`, backend encode, provider dispatch wait,
settlement/credit/quota) must never await, share, or be gated by harness-owned executor
futures, and stays measured. A follow-up optimization — full mock validation once per
unique upstream body with a cheap identity/short-circuit afterwards, legitimate because
every attempt in the envelope sends identical bytes — requires its own review before use
and is not part of this design.

This driver is labeled **thread-offload attribution, not client isolation**: worker
threads share the default executor with signed runtime work and contend for the GIL, so
thread-identity assertions prove execution location only — never independent
router-loop occupancy. Actual process isolation of the synthetic client would be a
stronger follow-up and requires its own design plus review; it is not authorized here.

1. Move only the boundary-listed client stages (SDK serialization, post-response
   checks) to a **dedicated harness executor** — never the default executor shared with
   router work — and measure plus report executor queue-wait time and the GIL-contention
   caveat alongside the loop metric. RSS stays aggregate parent+children including
   harness threads. All settlement, drain, reservation, 60 s load timeout,
   `failures ⊆ {"503"}`, `COST_TOLERANCE`/`KNOWN_*` and 503-accounting invariants stay
   identical; preencoded and full-SDK runs remain separate gates and neither replaces
   the other.
2. Prove workload identity by digest, not by length: capture one immutable fixture
   (fixed joint body bytes) and replay the identical bytes in both modes; the mock
   provider records SHA-256 per dispatched upstream request body, and equivalence is
   exact digest-sequence equality across modes (equal lengths never suffice, and
   independently seeded histories differ by random IDs and encrypted carriers).
   Admission schedule is deterministic for the equivalence run (single caller,
   sequential attempts, fixed stream alternation); scheduling-dependent completion
   counts are reported separately from workload identity and prove nothing about it.
   Byte-identity honors the post-serialization shim prohibition. Retain one unisolated
   full-stack run labeled contention-reference only, never a pass; offload-attribution
   artifacts use a distinct `scope` label (e.g. `sdk-thread-offload-attribution`) so
   they can never be filed as the original full-SDK gate passing.
3. If the offloaded router loop still exceeds 50 ms, that residual is **not** assigned
   to the router: shared-GIL contention with harness threads is acknowledged, so the
   residual requires isolated attribution measurements first (router-only loop probe
   with harness stages parked, plus executor/GIL controls) before any remaining latency
   may drive runtime design. Unattributed residual drives no runtime change; thread
   offload must not be used to explain away router work either. Both preencoded and SDK
   fixtures re-run for any harness change, with samplers, timeout, failure allowlist
   and artifact naming pinned against silent redefinition.

## Common requirements

- Same fixtures, envelope (sequential isolated 8x100, 512 MiB / 2 CPUs, network none),
  caps (128 MiB incremental RSS, 50 ms loop), and the full parent accounting — not a
  subset: exact native ordering/media/signature replay, bounded known usage, typed
  billing, input quota, zero active reservations, reusable capacity, no marker leakage,
  cancellation cases, validated-profile-only construction (no `model_copy`, test-owned
  startup-gate bypass only), and sealing headroom (context/wire/carrier bounds).
- Test-only harness changes first, each with focused tests (timestamp-matched
  attribution, 503-equivalence, snapshot isolation, orphan/reap,
  cancellation-while-preparing for Driver A; dedicated-executor thread-identity plus
  executor-wait reporting, upstream-digest equality under a deterministic schedule,
  wire/dimensions equality, reference-retention for Driver B); any runtime change
  needs its own feature-local design, full suite >= 80%,
  Ruff/format/mypy/Docker (+ Sonar scan if the script exists), deep review, docs, and
  relative-link/secret review. Historical failed artifacts are retained for comparison,
  with baseline/peak/incremental and wire-size fields still reported.
- Startup, live and production gates unchanged. Production remains memory-backed with
  `maxReplicas: 1`; no live inference is authorized by this design.
