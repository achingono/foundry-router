# Tools and Multimodal Activities

## Step-By-Step Activities

### T1 — Verify model, surface and client contracts

Confirm the [Inputs](inputs.md) references and re-inspect the predecessor once its code gate
passes. Build a dated model/surface/client capability table: function and parallel calls, schema
keywords/strictness, media forms, combined features, signature replay requirements, token/price
dimensions and safe limits. Use operator-selected IDs, never infer support from model names.

Pin strict synthetic request/response/SSE fixtures and client versions. Prove the exact client
can replay function output items, call IDs and required opaque state, including streamed results.
Choose a standard lossless carrier if available; otherwise write the opt-in continuation-extension
ADR, including caller binding, cryptographic library, key lifecycle, canonicalization and limits.
Do not implement an unreviewed public extension or claim tool support after state is dropped.

Record separate API decisions for audio/video input and generated image/audio output. Confirm
which capabilities need a native Google surface; otherwise retain compatibility. Independent
review must resolve public-protocol/signature decisions before dependent implementation.

**Output:** verified capability matrix, reviewed ADRs and fixtures; unresolved features remain
disabled. Contract research can precede the predecessor; dependent runtime work cannot.

### T2 — Extend configuration, validation and admission foundations (depends on T1 and predecessor)

Implement bounded feature profiles and supported combinations in `config/` and the adapter
capability interface. Default new features off. Reuse `supported_operations`; reject impossible
surface/model/profile settings and ensure homogeneous metering remains enforced. Filter by
features, combination and continuation binding before credit/quota reservation, on both selection
and failover. Exclude incompatible Google candidates without rejecting valid Azure requests.
Validate a logical-pool continuation policy before candidate selection: pools enabling required
signed state must reject missing carriers on function-call history even when healthy unsigned
alternatives exist. Keep unsigned tool workflows in separate pools; reject inconsistent profiles.

Implement bounded shared schema validation and media-size envelope checks. Add an internal
authenticated-caller scope only if the reviewed continuation mechanism needs it. Add its bounded
key configuration/readiness checks and redaction; never expose keys or scope derivation material.
Preserve server-owned reservation IDs and independent request authentication.
Bound all pre-admission schema/media/state work with an intake deadline/work budget. After
admission, preserve both its remaining lifetime and the original reservation deadline with
cleanup headroom; test expiration before reservation as well as during dispatch/streaming.

Extend estimation to instructions, tool declarations/schema, history/results and format overhead.
Define model-profile media bounds and all required price dimensions before enabling media. If
the current pricing/store shape cannot enforce a required dimension, record and implement the
smallest separate credit/quota boundary change with its own focused tests; never assume zero.

**Output:** fail-closed capability/estimate tests, configuration examples and typed inputs. No
unbounded media parser, provider token-count request or tool execution is added to routing.

### T3 — Function calls, results and signatures (depends on T2)

Implement the function mapping in [Capability contract](capability-contract.md): declarations,
choices, strict schema semantics, serial/parallel calls, text-plus-call output and complete result
history. Keep tool call IDs distinct from router output item IDs and billing request IDs. Validate
duplicates, orphans, names, argument completion, result size/order and parallel-result completeness.

If required by the enabled model, preserve signature-to-part association and emit/accept the
reviewed continuation carrier. Validate caller, backend/model/surface/configuration generation,
history digest, expiry and key version before admission. Pin continuation routing; do not fall
back to an unrelated healthy key. Exercise key rotation/restart and missing/changed configuration.
Test missing, stripped, partial and malformed carriers with healthy unsigned Google/Azure
candidates present: the request must fail
before any reservation or dispatch rather than degrade into an unbound continuation.

Implement streaming per-call argument assembly with strict byte/item bounds. Delay completed
status until arguments and required opaque state are validated. Handle interleaved calls, late
IDs/signatures, malformed arguments, truncation and cancellation; terminal usage may arrive later.

Use a local synthetic caller to perform request → call output → caller-produced result → second
request → answer. The router makes no tool call and creates no automatic turn. Add client tests
for preserved/dropped continuation extensions and honest capability rejection.

**Output:** Increment A function-call code and strict unit/integration/client tests. A
signature-dependent profile cannot pass its gate using a signature-free fixture alone.

### T4 — Structured output (depends on T2; combines with T3 only when supported)

Map JSON-object and strict JSON-schema text formats without weakening constraints. Validate
completed generated JSON locally with bounded work and no remote schema resolution. Test tool
arguments and structured text against allowed/unsupported keywords, local-reference cycles,
large enums, malformed JSON, strict failures, refusals and output-token truncation.

Stream provisional text/argument deltas under the existing commit rule; only emit successful
terminal outcomes after final validation. Failure after billable generation charges known usage
or the reservation. Do not retry a schema mismatch or repair JSON by generating extra tokens.

**Output:** Increment A structured-output code, tests and explicit supported schema documentation.

### T5 — Inline images and PDF documents (depends on T2; combined cases depend on T3/T4)

Implement narrowly scoped inline data parsing and verified public/provider media mapping. Start
with image formats whose dimensions can be bounded, then PDFs with bounded page/complexity
inspection. Enforce wire and decoded aggregate bytes, part count, pixel/page bounds, MIME/payload
agreement and parser work/deadlines. Reject remote URLs, foreign file IDs, paths and redirects
without outbound calls. Do not add upload, retrieval, rendering, OCR or transcoding services.

Apply media-aware quota/cost estimates before dispatch, including repeated history and multiple
media parts; enforce upstream limits. Unknown pricing or unavailable safe estimates fail closed
even on non-metered profiles for resource/quota dimensions. Measure parser/encoding/copy overhead
at supported concurrency within the body cap before permitting larger payloads.

Test mixed text/media ordering, image-plus-tool calls, image-plus-structured output, repeated
history, PDF content, unsupported formats, invalid base64, decompression/pixel/page bombs,
encrypted files, missing usage, failures and cancellation. Use tiny synthetic binary fixtures
with no personal content, generated by ordinary deterministic fixture tools where appropriate.

**Output:** Increment B image and document code gates independently recorded; combined features
enabled only when both provider support and integration tests pass.

### T6 — Native surface and additional media (per-capability T1 decisions plus T2)

Only add `api_surface` and a native adapter when a concrete selected capability requires it.
Keep native URL/auth mapping in the backend client and request/result/SSE conversion in the
adapter. Validate native text/tool/signature/usage contracts before enabling a media profile;
do not silently switch transports on a failed request. Preserve shared project and credit groups.

For each of finite audio input, video input, image output and audio output, first close the
public-schema, codec/parser, duration/frame/artifact bound, output framing, price/quota and
client-consumption decisions. Then implement one capability with its own tests and review.
Unsupported standard shapes require a reviewed versioned extension; absent that decision,
leave the capability Planned and reject requests explicitly.

Test compressed expansion, misleading media metadata, output bounds, safety/refusal outcomes,
usage details and cleanup. If no bounded public streaming representation exists, enable only
bounded non-streaming output and reject `stream: true` before egress. No media URLs are hosted.

**Output:** separate Increment C evidence per format/direction; native support and each media
type are independent claims. This step cannot close solely through a design decision.

### T7 — Cross-feature safety, documentation and code gates (each increment)

Cover capable/incapable mixed pools, three-or-more-key groups, signed-history pinning, per-attempt
quota, confirmed pre-dispatch retries, ambiguous dispatch termination, backend auth cooldown,
billable validation failures and exactly-once settlement. Exercise streaming cancellation and
slow consumers against the original reservation deadline, with independent close/store/metrics
cleanup failures. Repeated continuation requests must reserve/charge independently.

Assert synthetic API-key, prompt, argument/result, signature and media markers never appear in
errors/logs/metrics/admin status. Test safe exceptions from schemas/parsers and no remote schema,
media or tool egress. Review new dependencies and parser execution/resource boundaries.

Update API field/event examples and client compatibility, configuration/security, architecture,
routing, operational key rotation/drain notes, observability and requirements traceability.
Document disabled capabilities and native/extension limitations. Preserve Azure passthrough,
text/embedding behavior, homogeneous metering and the predecessor's retry/billing decisions.

Run new feature-focused adapter/schema/media/state tests first, then:

```bash
.venv/bin/python -m pytest tests/unit/ tests/integration/ -m "not docker and not azurite" --cov=src/foundry_router --cov-report=term-missing --cov-report=xml --cov-fail-under=80
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy src/
```

Complete Azurite/combined coverage, Docker build and image smoke gates as configured in CI.
Run `scripts/quality/sonarqube-scan.sh` if it exists (absent at this draft baseline) and address
all Blocker/Critical/Major findings. Run the independent
[deep-review prompt](../../../.agents/prompts/deep-review.prompt.md), address findings and
validate relative documentation links plus final diff/secret/status claims. Record unavailable
local gates and obtain required CI evidence before declaring code verification complete.

**Output:** per-increment reviewed code/docs, at least 80% implemented-code coverage and actual
verification results, without substituting predecessor or mocked evidence for live capabilities.

### T8 — Opt-in live verification and staged enablement (after each code gate)

Use actual operator-supplied model/client versions, secret references, project groups and finite
request/token/media/spend ceilings in an isolated memory-backed one-worker/one-replica app.
Exercise tool → caller fixture result → continuation, parallel calls, structured output, image
and PDF understanding, then each enabled Increment C modality and required combined features.
Execute only harmless local fixture tools in the test caller, never in the router.

Confirm signature preservation where required, actual usage/settlement, output consumption and
safe diagnostics. Do not deliberately exhaust provider quotas. Store only test case IDs, model/
client versions, results, usage counts and redacted operational observations; no prompts, outputs,
signatures, tool bodies or media content in retained live evidence. Keep synthetic fixtures separate.

Enable only the tested profile; disable a failing feature or drain/remove its backend to roll
back. Preserve supported old envelope keys until expiry when safe; documented key revocation may
require callers to restart conversations. No silent rerouting of pinned continuations. Production
enablement is a separate operator action under existing cut-over restrictions.

**Output:** exact live evidence per capability, or an explicitly Planned live gate when inputs
are unavailable. Code/client mocks alone do not establish real-provider or production support.

## Review Focus

- Does each client retain required tool/signature state through streaming and replay?
- Do features preserve semantics without execution, arbitrary egress or unbounded work?
- Can media/schema/signature failure under-account credit or bypass quota/continuation pinning?
- Are capability combinations, provider surfaces and incremental completion claims explicit?
