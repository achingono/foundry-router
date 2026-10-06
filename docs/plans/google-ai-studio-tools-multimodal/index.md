# Google AI Studio Tools and Multimodal Support

## Companion Documents

- [Inputs](inputs.md)
- [Activities](activities.md)
- [Outputs](outputs.md)
- [Exit Criteria](exit-criteria.md)
- [Risk Register](risk-register.md)
- [Evidence](evidence.md)
- [Capability and protocol contract](capability-contract.md)
- [Full requirement completion audit](completion-audit.md)
- [Image-format increment](jpeg-input/index.md)

## Status

**Partially implemented** (2026-10-05). The predecessor adapter is Implemented with mocked
verification at baseline `153b1b8`. The [reviewed implementation amendment](implementation/index.md)
delivers opt-in unsigned function round trips, serial/parallel SSE, JSON-object/strict-schema text
and bounded inline PNG input. The [image-format increment](jpeg-input/index.md) adds opt-in
baseline JPEG/static VP8L with measured local work limits. All capabilities default off. The public client gate uses OpenAI
Python 2.8.1; real Google inference and model-specific capability verification remain Planned.

## Objective

Preserve function identity, ordered history, output validation, conservative admission and
stream lifecycle while adding independently gated capabilities to the Google Responses adapter.

## Baseline and Prerequisites

- **Implemented:** predecessor typed adapters, operation filtering, bounded transport/SSE,
  usage, quota/credit cleanup and billable-failure settlement (mocked tests).
- **Implemented:** this amendment's unsigned tools, structured text, exact feature combinations
  and bounded small PNG/baseline JPEG/static VP8L input (synthetic/client tests).
- **Planned:** signed continuation carrier, larger images, PDFs, native transport,
  audio/video input and generated media. Their parser/protocol/pricing gates remain unresolved.
- **Planned:** real Google and production enablement; no live calls or deployment here.

## In Scope

- Caller-executed function declarations, tool choice, serial/parallel call output, function
  results supplied on subsequent Responses requests, and streaming argument events.
- JSON-object and strict JSON-schema text output only where semantics can be preserved and
  checked; shared bounded schema validation for tools and structured output.
- Lossless thought-signature/continuation handling with explicit client compatibility gates.
- Inline image input followed by inline PDF/document input, preserving mixed text/media order.
- Design and implementation gates for finite audio/video input and image/audio output; these
  require a verified public schema, transport, parser/resource budget and billing model before
  enablement. The plan does not assume Responses defines every media shape.
- Per-backend capabilities and supported combinations, safe model-pool selection, modality-aware
  estimates, bounded parsing/streaming, regressions, operator docs and opt-in live verification.

## Out of Scope

- Executing tools, opening caller files, running code, hosted web/search/MCP tools, computer use,
  automatic tool loops, or granting permissions based on generated function arguments.
- Public media uploads/storage, provider Files API lifecycle, arbitrary remote media retrieval,
  signed-URL relaying, URL-to-base64 proxying, server OCR/transcoding and general media hosting.
- Persistent Conversations/Responses, unbounded conversation caches, Realtime/WebSockets,
  live audio/video, Vertex AI, Google billing synchronization, or new cloud infrastructure.
- Multimodal embeddings, distributed quota/metrics, production cut-over and changes to the
  repository's requirement that production remain memory-backed with `maxReplicas: 1`.

## Delivery Increments

| Increment | Target | Entry dependency | Completion evidence |
| --- | --- | --- | --- |
| A — Tools and schemas | Stateless function round trips, parallel calls, structured text, continuation-state handling where required | Predecessor code gate; verified provider/client field contracts | Strict unit/integration/client fixtures; independent review; per-model live checks separately |
| B — Images and documents | Mixed text/inline images, then bounded inline PDFs | A's capability/admission foundation; image/PDF parsing and pricing gates | Ordering, media validation, cost/quota and combined tool/media tests |
| C — Additional media | Finite audio/video input and generated image/audio output, each independently enabled | Explicit schema/transport and pricing decision; native adapter only if justified | Separate protocol review and actual capability evidence for every enabled format/direction |

An implemented increment does not establish support for the next one. Images need not wait for
signature-dependent tool support, but tool-plus-image combinations require their combined gate.
Unverified capabilities remain disabled with clear pre-egress errors.

## Design Decisions

1. Extend the predecessor's `api/adapters/` boundary; retain transport/auth in `backends/`,
   admission in routing/credit/quota, and cleanup in forwarding.
2. Use Google OpenAI compatibility where it preserves the contract. Add a configured native
   adapter only when a required capability cannot use that surface. Never switch surfaces
   automatically after dispatch or to rescue a missing signature.
3. Start media intake with bounded inline content. Remote URLs and foreign file IDs are rejected
   before egress; media processing must not create new caller-controlled network destinations.
4. Require a lossless, tested continuation carrier before enabling signature-dependent tools.
   A versioned opt-in router extension is a candidate, not a claimed standard Responses field.
5. Keep every continuation a new authenticated HTTP request and new server-owned reservation;
   no tool call or continuation token grants execution, billing credit or idempotency privileges.

Details, proposed module ownership and hard decisions are in
[Capability and protocol contract](capability-contract.md).

## Entry Criteria

- Independently review this draft and record dispositions before implementation.
- Complete the predecessor code gate; confirm its interfaces and safety invariants still hold.
- Resolve T1 vendor/client compatibility and exact first-increment fields before dependent code.
- Enable a media modality only after bounded validation, estimation and pricing are defined.
- Supply actual test models, credentials, project grouping and finite request/spend limits only
  for opt-in real-provider validation. No live traffic is authorized by this draft alone.

## Exit Criteria

Use the per-increment [Exit Criteria](exit-criteria.md). Track implemented code, client round trips,
real provider validation and operational enablement separately. Never infer full coding-agent or
multimodal compatibility from text-only inference or a permissive HTTP mock.

## Roles

- Owner: Runtime/adapter contributor.
- Reviewer: Independent plan session, followed by independent implementation deep review.
- Approver: Project maintainer for public API additions and operational enablement.

## Current increments

[Full requirement audit](completion-audit.md) remains **Partially implemented**.
[Native/PDF local gates](native-pdf/evidence.md) passed; exact-model live validation remains pending.
[Signed continuation design](signed-continuation/design.md) is drafted for independent review and
public extension approval before runtime changes.
