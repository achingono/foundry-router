# Tools and Multimodal Exit Criteria

## Draft Gate

- [x] Predecessor plan committed and current tree/docs/source/tests inspected.
- [x] Templates copied and scope, contracts, dependencies, risks and quality gates written.
- [x] Independent plan review complete with findings addressed.
- [x] Documentation links, whitespace and final secret/status claims checked.

## Current code gate

The [implementation amendment](implementation/exit-criteria.md) records the passing restricted
unsigned-tools/structured-text/small-PNG code gates. The full modality/signature/live checklist
below remains the design target and is not claimed complete. The
[full requirement audit](completion-audit.md) maps each activity to evidence and remaining work.

## Prerequisites for Runtime Work

- [x] Predecessor adapter code gate passed and actual interfaces re-inspected.
- [ ] T1 vendor/client/capability contracts and necessary public API ADRs verified/reviewed.
- [ ] Profiles default new features off; exact combinations/surfaces are validated before routing.
- [ ] Needed schema/media estimates, price/quota dimensions and finite limits are defined.

## Increment A — Tools and Structured Text

- [ ] Declarations/choices/strictness map without semantic loss; undeclared tools rejected.
- [ ] Single/parallel calls and complete result sets preserve IDs, ordering and original turns;
  duplicate/orphan/reused IDs, malformed arguments and oversized schemas/results fail safely.
- [ ] Streamed argument deltas assemble by call index under finite bounds; completed call and
  response events require valid arguments/state; incomplete JSON never becomes a completed call.
- [ ] Router executes no tools and makes no automatic next turn; every caller continuation is
  independently authenticated, admitted and charged under a new server request ID.
- [ ] Required signatures survive actual pinned-client serialization, streaming and replay;
  missing/dropped state disables the affected capability rather than enabling a lossy fallback.
- [ ] Any extension has a reviewed schema, bounded authenticated encryption, internal caller/
  model/backend/surface/history binding, expiry and key rotation; bad state fails before egress.
- [ ] Pinned continuations never cross backend/model/provider/surface boundaries; repeated
  valid continuations reserve independently; restart/rotation/revocation behavior is tested.
- [ ] Bound-history pool policy rejects missing carriers before candidate filtering, including
  when healthy unsigned Google/Azure alternatives exist; unsigned workflows retain separate pools.
- [ ] Supported JSON-object/schema text and function arguments validate under bounded work;
  no remote `$ref`, silent strictness downgrade, JSON repair or success before final validation.
- [ ] Refusal, token limit, late schema failure, cancellation and ambiguous dispatch preserve
  predecessor stream, cooldown, quota and conservative credit-settlement policies.

## Increment B — Images and Documents

- [ ] Image input and PDF input pass their own format/type/pixels/pages/bytes/work gates.
- [ ] Public/provider mappings preserve text/media ordering, roles and supported detail settings;
  no base64-as-text, filename substitution or manufactured summaries.
- [ ] Remote media URLs/file IDs/local paths and embedded fetch instructions cause no egress;
  schema validation and tool handling create no additional outbound destinations.
- [ ] Wire/base64-decoded/aggregate caps, corrupt media, MIME mismatch, encrypted files,
  decompression/pixel/page bombs and parser cancellation are tested with bounded memory/work.
- [ ] Modality estimates include tool/history overhead and verified conservative media bounds;
  missing prices/estimates fail closed; non-metered keys still obey resource/quota limits.
- [ ] Concurrency measurements justify enabled payload limits; defaults are not raised without
  evidence; required image/tool/schema and PDF combinations have separate passing tests.

## Increment C — Additional Media (Repeat for Each Format/Direction)

- [ ] Public schema is documented and verified, or an explicit versioned extension reviewed;
  unsupported Responses media fields are never presented as standard.
- [ ] Native surface added only if needed and independently verifies tools/signatures/usage
  with fixed URL mapping, configured credentials and shared quota/credit identity.
- [ ] Codec/type/duration/frame/output-artifact bounds and conservative price/quota dimensions
  are validated before the capability is enabled; parser resource isolation is reviewed if needed.
- [ ] Public output/stream framing is bounded and client-consumable; unsupported streaming
  is rejected before dispatch; no new hosting/upload/media retrieval path is introduced.
- [ ] Refusal, truncation, media conversion failure, missing usage and cleanup pass lifecycle tests.

## Shared Code and Live Gates

- [ ] Mixed provider/pool eligibility and capability combinations pass; existing Azure,
  text/embeddings, homogeneous metering, health and shared-credit regressions remain green.
- [ ] No retry after downstream output or ambiguous Google dispatch; argument/media failures
  after generation retain consumed quota and charge actual usage or the full estimate.
- [ ] Intake deadline/work limits bound schema/media/state validation before admission; the
  remaining intake lifetime and original reservation deadline bound dispatch/backpressure/cleanup.
  Close/store/telemetry failures cannot orphan cleanup or authorize a second dispatch.
- [ ] Synthetic secrets, signatures, prompts, tool bodies and media markers absent from logs,
  errors, metrics and admin diagnostics; validation failures have safe bounded messages.
- [ ] Focused/full tests, at least 80% coverage, lint/format/type checks, required CI/Azurite,
  Docker build and image smoke pass; Sonar script run if present; findings addressed.
- [ ] Independent implementation deep review, canonical docs/traceability, links and final
  secret/status diff checks complete for each claimed increment.
- [ ] Separate opt-in bounded live tests pass for exact model/client/capability combinations;
  test-only inputs, usage/settlement and safe evidence/cleanup recorded.
- [ ] Production enablement remains separate; untested features/clients/modalities stay Planned.

Do not mark this entire plan complete merely because tools or image input work. Report each
increment's code and live gates; unresolved native/media/continuation decisions remain explicit.

## Approval Table

| Role | Name | Status | Notes |
| --- | --- | --- | --- |
| Draft author | Codex | Prepared | Planning only; predecessor implementation remains pending |
| Independent reviewer | `review_tools_multimodal_plan` session | Reviewed | One Major finding and one Suggestion addressed; no blocking plan findings remain |
| API/release approver | Project maintainer | Pending | Future extensions and enablement are separate decisions |
