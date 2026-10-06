# Native Google transport and bounded PDF input

**Partially implemented** increment of the full [parent plan](../index.md), following bounded image gates.
Native foundation passed independent implementation review; PDF parsing remains Planned.

## Companion documents

- [Inputs](inputs.md)
- [Activities](activities.md)
- [Outputs](outputs.md)
- [Exit criteria](exit-criteria.md)
- [Risk register](risk-register.md)
- [Evidence](evidence.md)

## Objective and concrete dependency

Google's current compatibility documentation establishes tools/images/audio, but no inlinePDF
Chat mapping was verified. The native generateContent reference establishes contents/parts with
inlineData MIME/data and application/pdf in supported documentation. Add explicitly configured
native transport for this document requirement; retain provider identity/shared groups and never
switch surfaces automatically. Native text/tool/schema/image and usage gates precede PDF enablement.
No provider Files API, Interactions storage, uploads, media hosting, fetch, OCR or transcoding.

## Native contract

Backend `api_surface`: `openai_compat` default or `native`, Google-only. Native accepts responses
operation only; explicit embeddings/native combinations fail startup. Transport maps configured
endpoint root plus `/v1beta/models/<quoted deployment>:generateContent` or
`:streamGenerateContent?alt=sse`, using x-goog-api-key. Body cannot choose path/query/version;
stream selection comes only from owned stream_backend path. Reject compatibility suffix on native
configuration; no model body rewrite/injection for native. Same backend/quota/credit identity.

New native adapter behind the existing protocol reuses bounded public request/tool/schema/history
validation and local output context. Map ordered messages to native user/model contents/text,
input images to inlineData preserving order. System/developer/instructions require a concrete
normalization decision: native has systemInstruction, so reject system/developer messages after
non-system history; join only the leading system text preserving order. Do not reorder mid-history
system instructions. Function declarations carry unchanged bounded parametersJsonSchema; choices
AUTO/NONE/ANY/allowedFunctionNames, serial/parallel output enforced locally. Function-call ids must
be nonempty provider IDs (never infer/mint replay IDs); native functionResponse wraps string
results in `{output: <string>}` with original id/name. Required provider state/thought parts fail
closed until the signed-carrier increment. No automatic tool execution or extra turns.

JSON-object maps responseMimeType application/json; strict schema additionally responseJsonSchema,
unchanged constraints and final local validation. No native strict flag exists; the API guarantee
is validated final output, preserving unchanged schema. Native thinking disabled by an explicit
operator model affirmation and thinkingConfig.thinkingBudget=0; reject thoughtSignature/thought
output safely. Models that cannot honor disabled thinking remain ineligible until signed/usage
contract closes. Future signed-native profiles are independent.

Single candidate index0, role model, bounded parts text/functionCall only; convert to existing
Responses output implementation using request-local context. STOP completed, MAX_TOKENS incomplete,
SAFETY/RECITATION/BLOCKLIST/PROHIBITED_CONTENT/SPII mapped safe incomplete/refusal, other outcomes
billable safe protocol errors. Native usageMetadata promptTokenCount input; output is
candidatesTokenCount+thoughtsTokenCount, cache tokens already included in prompt. Validate totals
and integer/nonnegative bounds before translation; unknown toolUsePromptTokenCount or nonzero
reasoning on disabled-thinking profile fail safely while retaining conservative known usage if
possible. Missing usage keeps full reservation; no double counting or provider balance claims.

Native SSE has no Chat `[DONE]`. Separate decoder must parse finite SSE events/parts and finish
reasons, preserve stream commitment/deadline/late usage, and generate terminal response only on
clean native EOF with an observed valid finish. EOF without finish, malformed usage/parts or
truncation fails. Text deltas provisional; complete native functionCall args may produce a single
arguments delta after validation, without fabricated timing. Pin actual OpenAI SDK accumulation.
Adapter owns conversion only; forwarding retains retry/cooldown/settlement/cleanup.

## PDF parser/resource decision to review before PDF code

The [concrete PDF preparation contract](pdf-design.md) specifies the separate worker,
immutable metadata flow, admission limits and conservative accounting for independent review.

Initial public Responses input_file: only inline file_data data:application/pdf;base64 plus safe
ASCII display filename ending.pdf, no file_id/file_url/paths. Native maps inlineData unchanged;
filename never becomes a path or text substitution. Profile `inline_pdfs` default off, exact
combinations, maxPDF bytes64KiB, max4 documents/max4 pages aggregate, required conservative token
ceiling at least258/page plus bounded extracted-text ceiling and overhead, token-price affirmation.
Google-only native logical pools; pool-wide maximum estimates and all nonmetered resource gates.

Do not use an unrestricted in-process PDF parser. Proposed vetted pypdf subprocess worker reads
bounded bytes from stdin, writes only small validated metadata to stdout, never media to disk.
Fresh worker has CPU/address-space/file-size/fd resource limits, parent wall timeout and bounded
pipe output; no prompt/media in errors. Reject encrypted PDFs, external references/actions,
embedded files/scripts, object streams/xref streams, filters/compressed content, unbounded object
count/reference depth/page trees and malformed cycles. No rendering/text extraction required for
routing. A worker absence/failure fails capability readiness/pre-egress. Review portability and
container limits before implementation; parser isolation must not cause blocking event-loop work.

Async pre-admission PDF preparation belongs to API boundary, before routing reservations, with
original intake deadline and bounded concurrent worker slots. Immutable request-local metadata
is internal, excluded from public body, upstream transport, logs/admin and history replay; never
trust caller-supplied counts. Candidate adapter checks cached validated metadata only where its
own limits permit. Avoid repeated subprocesses on selection/build/failover. Actual architecture
must be reviewed before adding metadata fields/call arguments; no body mutation/caller bypass.
PDF resource/estimation implementation stays disabled until this mechanism and pricing are tested.

## Gates and roles

First review native text/tools/schema/images/usage/transport, implement/test minimal native
foundation. Then resolve/review async isolated PDF preparation and estimates before dependent
PDF code. Independent session reviews each concrete contract; API extensions need maintainer
approval only if introduced. Native/document uses standard public fields, no new public extension.
Live exact model/credentials/spend inputs remain pending and distinct from local code.

## Independent native review dispositions (before runtime edits)

- Usage: require totalTokenCount==promptTokenCount+candidatesTokenCount+thoughtsTokenCount when
  supplied, cachedContentTokenCount<=promptTokenCount, toolUsePromptTokenCount absent/zero.
  Independently retain known billable dimensions even when unexpected nonzero thought/tool
  usage rejects: normalize input conservatively including tool prompt if nonzero, output
  candidates+thoughts; if totals inconsistent or a dimension invalid, full estimate rather than
  underbilling. Stream usage is cumulative replacement with monotonic dimensions, never sum.
  Extract usage before any output conversion, including same-chunk failures/cancellation.
- Content role/order: coalesce only adjacent same-role public message parts preserving order;
  assistant text/calls from one reconstructed turn remain one model Content. Each complete
  parallel result set becomes one user Content with ordered functionResponse parts/id/name;
  ordinary following user text can append to that user Content. No role tool is sent native.
  Only leading system/developer/instructions are combined in order into systemInstruction;
  mid-history system/developer items reject, no reordering.
- SSE: clean EOF requires empty framing buffer and observed finish. Reject content/function
  parts after finish; allow usage-only late envelopes. Complete native argument objects remain
  provisional until final response validation; native EOF finalization remains bounded by
  original reservation/intake deadline and downstream no-retry commitment.
- Forwarding integration: add typed adapter usage extraction (or equivalently narrow helper)
  at owning boundary and use it independently in nonstream output-failure/cancel paths, stream
  decode/prefetch/cancel. Azure retains current behavior; Google compat unchanged. Native decoder
  owns native SSE/EOF and may reuse public event construction only after strict native fields
  validated. Do not fabricate Chat raw envelopes/[DONE] upstream or discard native state/usage.

Known promptFeedback.blockReason with no candidates is accepted only for SAFETY, BLOCKLIST,
PROHIBITED_CONTENT or OTHER, mapped to a fixed safe refusal/incomplete content_filter outcome;
no provider safety text is exposed. Empty candidates without known block evidence fail. Candidate
finish mappings accepted: STOP, MAX_TOKENS, SAFETY, RECITATION, BLOCKLIST, PROHIBITED_CONTENT,
SPII; other values fail conservatively. Pin synthetic no-candidate block fixtures/usage cleanup
and actual SDK refusal accumulation alongside native text/call fixtures.
