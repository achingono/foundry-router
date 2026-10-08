# Full-plan completion audit

**Partially implemented**, audited 2026-10-06 against the parent activities and exit criteria,
reconciled 2026-10-07 (status rows only; no gate claimed). The 2026-10-06 baseline below is
historical: several rows then listed as outstanding now have reviewed implementations under
the startup gate, with resource/live/enablement as the remaining blockers — updated inline.
The restricted implementation amendment is evidence for individual rows only. It does not
replace the full plan. A checked local code gate does not establish live provider compatibility.
Exit-criteria checkboxes remain entirely unchecked: implementation evidence alone does not
check a plan gate, which additionally requires maintainer approval plus its resource/live
proof. Do not read an updated row as a checked box.

## Delivery triage (2026-10-07 maintainer direction)

The full plan is no longer the prerequisite for every row. Work splits three ways:

- **Required now:** modern-model text (3.5-flash-lite `minimal`, 3.8-flash `low`;
  separate bounded track in [thinking-level-text-design](live-runner/thinking-level-text-design.md)),
  streaming text on the same profiles, project/model quota routing with exclusion of
  inaccessible combinations, thought-inclusive usage settlement, and request/usage
  cleanup. 2.5 text stays on its proven budget-0 path outside the new track.
- **Deferred:** PDF/image/audio/video input, generated image/audio output, and maximum
  signed-history resource benchmarks. No further benchmark or media work is required
  for the text track; historical failed artifacts stand as recorded.
- **Conditional:** function tools and signed continuation, for coding-agent clients
  only — each needs its own round-trip validation before any claim.

Rows below keep their evidence links; triage changes priority and gating order, not
past evidence.

| Requirement | Current evidence | Remaining work |
| --- | --- | --- |
| T1 dated exact model/surface/client capability matrix | Official compatibility/image/function sources and pinned OpenAI Python 2.8.1 fixtures in [contract](implementation/contract.md) | Exact operator model IDs, signed and remaining media contracts, per-combination live evidence |
| T1 lossless continuation/public extension decision | Signature-bearing output safely rejected; reviewed codec/key/history/adapter/stream/integration under the startup gate in [signed evidence](signed-continuation/evidence.md) (2026-10-07: also sealed-profile HTTP, expiry/rotation/revocation and fresh-process replay) | Schema approval; maximum combined resource/lifecycle/live gates before enablement |
| T1 additional-media API decisions/native justification | Parent identifies gates; unsupported shapes rejected | Separate finite audio/video and generated image/audio decisions based on current documented transport/public schemas |
| T2 default-off bounded exact capabilities | [Profile code](../../../src/foundry_router/config/google_features.py), configuration/combination tests | Additional profiles after each protocol/parser/accounting gate |
| T2 pre-reservation selection/failover eligibility | Existing Google/Azure and exact-combination tests | Signed pinning/missing-state HTTP tests pass under startup gate; complete lifecycle/resource review pending |
| T2 caller binding/key readiness/redaction | Reviewed codec/key/auth helpers plus secret-only key configuration, domain-separated caller scope and key-snapshot intake binding ([evidence](signed-continuation/evidence.md)) | Runtime integration added under startup gate; concurrency/deadline/lifecycle gates remain |
| T2 bounded intake, reservation lifetime/cleanup | [Reviewed intake/worker hardening](signed-continuation/runtime-hardening.md), deadline and lifecycle regressions, plus early body admission with capacity/slot-accounting proofs | Resource checks rerun on reconciled runtime (quote-heavy and first joint signed-PDF runs fail RSS/loop caps, recorded as evidence); combined state/media gates remain |
| T2 conservative text/tool/schema/image accounting | UTF-8 upper bounds, 258 minimum small-image ceiling, Google-only media pools | Larger/PDF/audio/video/generated-media price/quota dimensions and verified upper bounds |
| T3 declarations/choices/calls/results | Explicit strictness; names; distinct IDs; complete ordered serial/parallel histories | Required signed-state association/validation |
| T3 signed continuation validation/routing | Reviewed implementation under the startup gate ([evidence](signed-continuation/evidence.md)): owned caller/backend/model/surface/config/history binding, repeated HTTP replay/billing, expiry/key overlap/revocation, fresh-process replay, ASGI delivery and early body admission with slot-accounting tests — not merely unattached helpers | Maximum combined resource/lifecycle/live gates before enablement |
| T3 argument SSE assembly | Actual SDK stream state fixtures, interleaved/fragmented calls and contiguous indices | Late signatures, signed incomplete/stripped-state fixtures |
| T3 synthetic caller round trip | Nonstream and streamed unsigned full-history replay | Exact-client signed extension retained/dropped-state gates |
| T4 bounded JSON-object/strict-schema semantics | Bounded subset, no remote refs/normalization, final validation | Exact model/combinations live evidence; larger subset only if required and safe |
| T4 refusal/truncation/billable mismatch | Tests preserve usage or full reservation; no repair/retry | Corresponding new-media/signed lifecycle cases |
| T5 image public/provider mapping | Inline PNG ordered text/media with auto detail | [JPEG/VP8L local gate passed](jpeg-input/evidence.md); larger-image/lossy-WebP gate |
| T5 PDF mapping and bounded page/type/complexity inspection | Partially implemented native input_file, isolated finite parser, immutable facts; [local PDF gate passed](native-pdf/evidence.md) | Exact model/pricing/live evidence before enablement |
| T5 media aggregate/resource/no-egress bounds | PNG/JPEG/VP8L byte/pixel/container/raster/work, remote URLs/files rejected | [Local concurrent measurements](jpeg-input/evidence.md) passed; larger/document/additional media gates remain |
| T5 media-aware cost/quota/history | Small-image ceilings with framing/history overhead | PDF/larger-image upper bounds and all required accounting dimensions |
| T5 combined media/tools/schema/failure tests | PNG/JPEG/VP8L combinations/usage/deadline tests | PDF local combinations passed; new-media cancellation coverage |
| T6 configured native surface | [Native foundation locally reviewed](native-pdf/evidence.md): fixed URL/auth/shared groups/text/tool/schema/image, SDK ordered replay and usage fixtures | Exact-model live validation; signed/native additional-media contracts |
| T6 finite audio input | [Finite WAV partially implemented](audio-input/evidence.md); review, SDK and audio-only Linux gates pass | Combined media/state resource, cancellation, final quality and exact-model live gates |
| T6 finite video input | [Finite raw DIB AVI partially implemented](video-input/evidence.md); review, SDK, candidate/lifecycle and video Linux gates pass | Combined resource/final quality/exact-model codec/pricing/TPM/live gates |
| T6 generated image output | [Partially implemented under startup gate](generated-image/evidence.md): native mapping, standard SDK artifacts, worker/readiness, full image settlement and quota prerequisites | Local exact maxima/weighted combined resource/delivery/drain and final verification passed; exact-model live paid gate |
| T6 generated audio output | [Gated generated WAV integration](generated-audio/evidence.md): reviewed versioned SDK carrier, finite parser/native mapping, pricing/quota/billing and actual delivery/cancellation tests; max/invalid Linux checks pass | Local mixed-capacity Linux/SDK/billing/lifecycle/deep review cleared; exact-model live gates |
| T7 mixed pools/groups/retry/billing | Existing full suite and feature admission/settlement regressions | Signed pinning/repeated HTTPbilling passed; new-media candidate/accounting cases remain |
| T7 cancellation/slow clients/cleanup failures | Existing deadline and retained-usage prefetch tests | Signed worker timeout/cancellation, direct ASGI blocked-send and bounded fresh-process cleanup tests passed; realdisconnect/combinedmedia cleanup remain |
| T7 secret/content redaction/no extra egress | Existing safe errors and restricted adapter architecture | Explicit signed/new-media marker regressions and dependency/resource review |
| T7 canonical API/config/security/ops/traceability | Updated for implemented subset | New features and key rotation/drain behavior as implemented |
| T7 quality/deep review | Latest reconciled local:1509 passed,88.86%; prior14actualAzurite; Ruff/mypy; Python3.12 Docker smoke; independent review, [evidence](native-pdf/evidence.md) | Final docs links and gates after additional increments; Sonar conditional script absent |
| T8 opt-in live runner and exact capability evidence | Five model-list GETs discovered61models/project,44generateContent; [dormant runner/ledger](live-runner/evidence.md) and all-model manifest partially implemented | Exact protocol/free-tier capability review and guarded execution, generated media and signed startup gates; zero inference so far |
| T8 full-plan status and production separation | Explicitly partial; production unchanged | All code/client/live rows proven before full completion; production remains a separate gate |

## Next increment

The [image-format amendment](jpeg-input/index.md) closes bounded JPEG/VP8L and local concurrency evidence.
Signed runtime remains gated despite local codec/client/lifecycle progress; aggregate state resource gates and each Increment C direction remain required follow-up work.
Live authorization is recorded; exact protocol cases and guarded execution remain incomplete.

## Remote reconciliation

Remote `45cbb70` is integrated on main with preserved local changes. Its fixes cover Azure
execution versus intake deadlines, safe non-list provider-state checks, embeddings intake, exact
PNG raster completion, transient PDF readiness and bounded inspector orphan cleanup. Local
worker lifetime/redaction, strict canonical depth, owned snapshots, scanner and early body
admission changes coexist. The full reconciled suite passes 1,509 tests with 88.86% coverage.
Actual discovery artifacts are preserved separately from the remote synthetic offline fixtures;
no inference or production change occurred. Remaining resource/live gates remain incomplete.
