# Signed native continuation design

**Planned**,2026-10-05; independent API/design review required before code. This is the T1
proposed concrete decision for the provisional foundry_provider_state extension. Independent
review gates runtime implementation; maintainer API approval gates operational enablement.
The user-authorized implementation remains reversible and default-off until that approval.

## Public negotiation and finite profile

Fresh bound-history requests explicitly include `foundry_provider_state: {"version":1}` at the
request root. Output function_call and assistant message items each carry
`foundry_provider_state: {"version":1,"token":"<opaque sealed turn>"}`. Full-history continuation
replays all completed output items unchanged plus caller tool results. Negotiation is required
on every request. Other fields/versions reject. This is a router extension, not standard Responses
reasoning/encrypted_content. Nonparticipating clients cannot use the bound-history pool.

Pool continuation policy `bound_history_required` is distinct from default unsigned behavior.
Initially every backend in that pool must be signed native Google with the same support contract;
reject mixed unsigned/Azure members at startup rather than permit an unbound tool producer.
Any assistant/function_call history requires state before candidate filtering. Fresh user-only
requests may route among configured signed backends; stateful histories pin original backend.
Backends opt in `continuation_policy="sealed_native"`; compatibility remains unsigned only.
Configure explicit bounded native thinking budget0–8192 and token-price equivalence affirmation
for thought tokens. Existing unsigned native thinking-disabled affirmation remains unchanged.
Total provider maxOutputTokens covers candidates+thoughts, reservation includes configured thinking
budget conservatively if provider contract is uncertain; live gate must verify exact inclusions.
Thought text/output (`thought:true`) remains unsupported and fails safely with known usage retained.
Only ordinary text and functionCall Parts with optional thoughtSignature are accepted.

## Exact association and envelope

Preserve every provider Part boundary, including adjacent text Parts, without merge. Each text Part
becomes one output message; each functionCall one function_call. Envelope holds opaque signatures
associated by exact part ordinal/type, plus digest of each unsigned native Part. Do not include
prompts, raw output or arguments inside envelope. Preserve original signature string exactly after
canonical base64 validation; max16KiB decoded/signature and64KiB decoded aggregate/turn.
Bound64Parts. A signed tool turn must contain at least one signature; otherwise billable failure.
Unsigned ordinary text-only turns in a signed pool still receive an envelope with empty signatures
so their backend/history is bound. Signature-only/empty text Parts, unknown metadata and thought
Parts reject until separately reviewed. Preserve function IDs and args semantics without synthesis.

Use cryptography Fernet (authenticated encryption), pinned dependency reviewed before install.
Settings hold dedicated stable caller-scope key and1–3 Fernet keys with bounded ASCII key IDs,
active key ID, server configuration generation and state TTL60–3600seconds (default900). Values
are secret/excluded/redacted; no raw credential/backend secret in envelope. Caller scope is
HMAC-SHA256(dedicated scope key, matched client credential), nonpublic Request state. The scope key
is separate from envelope keys so decrypt-key rotation preserves caller binding.
Token wrapper selects allowlisted key ID; authenticate before trusting version/payload. Plaintext
contains version,key ID,expiry,caller scope,logical model,backend ID,configured deployment/surface,
server generation, safe backend-config fingerprint (no credentials), response ID, ordered item IDs,
start history index,history digest,part digests and signatures. Bind credential rotation through
HMAC-derived backend credential fingerprint under scope key. Token bound is `min(128KiB, floor(256KiB / output_item_count))`; count the full
wrapper UTF8 bytes, including repeated occurrences, not unique ciphertext only. All carrier
occurrences in input total<=512KiB, at most16 unique turns. All output wire bytes including
repeated carriers remain within4MiB; check before public completion. Signatures meeting individual
limits can still exceed aggregate envelope/occurrence limits and safely fail as a billable output
protocol error. Do not silently drop signatures to fit. Dedupe identical authenticated tokens
for decryption work only, preserving every occurrence in byte accounting. Exclude repr/logging. Enforce bounded duplicate-free JSON and ints.
Fernet own timestamp and explicit expiry validate with bounded clock semantics. No conversation cache.

## Canonical history and owned context

Digest a protocol-owned projection of all replay history through the signed turn, excluding the
extension shallowly only at allowed negotiation root and output-item root locations. Require output ids/call_ids/order/args
bytes/text/media data identical; do not silently normalize whitespace or signatures. Include initial
instructions and tool declarations and response-format contracts in request-context digest, so edits
require a fresh conversation. Exclude stream/max_output_tokens/metadata because continuation requests
may change transport/output budget. Project accepted standard message optional status to completed
for completed output replay only; pin a reviewed normalization table and SDK fixtures. Canonical
JSON uses sorted keys, ensure_ascii=False, compact separators, allow_nan=False, strict UTF8 and
SHA256; global2MiB intake + finite history/work bounds apply before decryption.
Canonicalize bounded projected history once, store cumulative byte offsets and hash prefixes
incrementally using SHA256.copy at signed boundaries; total projection serialization/hash work
<=2MiB/request rather than16 complete reserializations. Context serialized once<=128KiB.
Only16 distinct token decryptions, total unique decoded envelope bytes<=512KiB; validate aggregate
carrier occurrence bytes and item/turn caps before decryption. Check intake deadline between
bounded crypto/projection steps and benchmark64Parts/signatures/repeated carriers.

Every item of a turn carries the same token; verify exactly all ordered item IDs contiguous, token
identical and projection digest, then reconstruct native Parts from public content and reattach
signatures to their bound ordinals. Original part digest must match reconstructed part. Previous
turns must independently validate; all tokens in a request bind same backend/model/config. Caller
results follow completed call turn and remain inert text. API creates frozen PreparedContinuation
with safe backend identity and tuple signatures/positions, explicit optional parameter through
adapter/routing/forwarding; no caller body mutation/global cache/contextvar. Adapter instance receives
per-request nonlogging seal context owned by API/transport; adapter does no secret lookup or routing.

## Streaming and failure lifecycle

Initial signed Responses stream uses a configured native generateContent nonstream upstream
request, then emits bounded public events from the validated complete response. This is an
explicit signed-profile transport contract, not retry/failover or automatic surface switching.
Backend transport receives API-owned `native_generation_stream=False` even when downstream
body.stream=true; caller cannot select a route. Every original Part is available in one complete
native response, so text/signature association has no SSE fragment ambiguity. Preserve the
4MiB bounded upstream body/output limits; emit one bounded argument delta only after validation
followed by finalized items/state and terminal snapshot. Document added time-to-first-event.
No streamGenerateContent signed support is claimed: independent native SSE arrays have no stable
Part indices, and fully buffering them cannot distinguish fragments from adjacent signed Parts.
A later transport requires a separate documented identity contract before enablement.

Complete native output and signature association are validated before any output-item completion;
sealing happens before public emission. Missing/invalid state is a billable failure retaining
known candidate/thought usage or full reservation. Slow-client delivery retains the original
reservation deadline, cleanup ownership and no-retry-after-output invariant. Cancellation before
public output does not authorize retry after ambiguous dispatch.

Invalid/missing state yields safe422 invalid_provider_state before reservations. Pinned healthy
backend undergoes normal quota/credit admission; unavailable returns429/503 with no failover to
another backend. Repeated valid continuation is a new independently billed request, not a replay
prevention token. Removed/generation-changed backend or client-key rotation requires fresh history.
Same keys/config across restart validate; bounded overlapping decrypt keys permit rotation; deletion
revokes. Cancelled/invalid provider turns retain known valid thought/candidate usage or reservation.

## Concrete projection and key rules

Signed v1 initially accepts only list input; user text shorthand input string is rejected so
conversation item positions remain explicit. Accepted fields are the existing strict native
Google history subset, with foundry_provider_state additionally allowed only on assistant
message/function_call items. No recursive unknown-field stripping.

| Item | Accepted keys | Canonical defaults and preservation |
| --- | --- | --- |
| User/system/developer message | type,id,role,content,status | type absent becomes message; role required; status absent becomes completed; optional id is retained exactly when present; content string/list remains distinct and exact |
| Assistant signed message | type,id,role,content,status,foundry_provider_state | Require type message,id,role assistant,status completed and exactly one output_text part with exact text and empty annotations; no logprobs/refusal/unknown fields; exclude only its carrier from digest |
| Function call | type,id,call_id,name,arguments,status,foundry_provider_state | All keys required; completed status; arguments exact string bytes retained in history digest; preserve item and call IDs/name |
| Function result | type,id,call_id,output,status | type/call_id/output required; status absent becomes completed; optional id retained; output exact inert string |
| User content | existing input_text/input_image/input_file strict subset | Exact ordered part objects and data URIs; preserve optional detail/filename when present; no coercion |

Reject explicit null status/type/id and missing required signed IDs. Assistant content from the
SDK final snapshot must retain annotations=[]; extra optional logprobs=None is omitted by
model_dump(exclude_none=True); explicitly supplied null/other logprobs reject. On sealing, use
the exact finalized public output projection with type/status/IDs populated by router. Never
construct the digest from caller-supplied page counts or mutable post-await values.

Context digest fields: instructions absent is empty string; explicit null rejects; string
bytes preserved. Tools absent is []; tools retain ordered exact validated declarations with
explicit strict, required parameters/name/type, optional description preserved (absent differs
from empty). tool_choice absent is auto, otherwise exact validated choice. parallel_tool_calls
absent resolves to configured parallel_calls feature, otherwise exact boolean. Text absent or
{format:{type:text}} projects to plain-text enum; json_object/json_schema retain all validated
fields/defaults without schema rewriting. Include server-derived thinking config/output modality
and exact profile generation. Exclude only root negotiation,stream,max_output_tokens and metadata.
All other allowed root fields that influence generation must either enter context digest or
be rejected in signed v1; do not inherit a permissive unsigned field pass-through.

Native Part digests canonicalize sorted JSON semantics of server-normalized function args
validated by duplicate-free bounded JSON, rather than raw provider dict key order. Public
arguments retain exact router-emitted bytes separately in history digest. Text Part digests
preserve exact Unicode text. Snapshots/projection/signature association captured synchronously
before any await and immutable facts validated against body digest on check/build/failover.

Scope keys require32 random decoded bytes; Fernet keys require32 decoded bytes. Domain separate
HMAC caller\0credential and backend\0credential. key IDs1–32 ASCII alnum/underscore/hyphen,
1–3 unique decryption keys, reject duplicate key values or reuse with caller-scope key. Active
key must be present. Fingerprint includes configured endpoint/deployment/provider/surface,
quota/credit project identity, thinking/native config, enabled features/combinations/all limits,
pricing equivalence/ceilings and credential HMAC; no raw secrets. TTL60–3600seconds. Authenticated
issued_at/expiry integers satisfy expiry=issued_at+mintedTTL; valid mintedTTL bounded, currentTTL
may restrict lifetime but never extend it. Fernet issuance timestamp must equal issued_at; reject
issuance>now+60seconds and expiry<now with no expiry grace. Rotation preserves original timestamps.

Seal replayable output only on completed STOP with validated entire output and all call args/
signatures. MAX_TOKENS, safety/refusal and incomplete outcomes emit incomplete/nonreplayable
items without state and never completed function calls; clients must start fresh rather than
replay those items in the bound-history pool. A text-only STOP turn is sealed, with empty opaque
state permitted, preserving backend/history binding. Explicit safety/refusal remains a billable
terminal outcome, not a signed conversation continuation.

## Signature accounting and expiry

PreparedContinuation carries a conservative signature input estimate separate from public
carrier bytes: sum original validated canonical base64 signature UTF8 lengths plus64tokens/
signed Part (at least one token per actual base64 byte; no unsupported claim signatures are
unbilled). Pool admission uses the maximum enabled aggregate signature estimate bound; quota
TPM and credit share this token estimate before dispatch. Exact provider signature/context
accounting must be affirmed before live enablement; no safe token bound keeps feature disabled.
Router ciphertext occurrence bytes never become provider prompt tokens or egress; estimate
ordinary projected history after removing only allowed item carriers, then add server-owned
signature bound. Missing/malformed usage reserves full bound; valid native prompt/candidate/
thought totals settle once. Free-tier token admission remains conservative despite zero dollars.

Never exclude same-named fields inside tool schemas, argument strings, results or nested data.
Reserved carrier on user/results/unknown item shapes rejects. Native reconstruction groups a
sealed turn into its exact ordered original Parts; it does not collapse adjacent text Parts or
merge different signed turns. Every earlier turn token validates independently; conversation
continuation expires at the earliest retained token. Replay/key rotation never renews expiry,
and callers start a fresh stateless history after expiration.

## Seal admission and wire wrapper

Input512KiB occurrence budget counts canonical serialized public carrier objects (version/token),
including their JSON wrapper. Codec per-turn token budget is preliminary; seal admission also
checks repeated complete public carrier objects under256KiB.

Public token string is `<key-id>.<canonical-url-safe-Fernet-token>` with exactly one separator.
Validate key ID and encoded length before selecting a configured key; canonical URL-safe base64
checks reject alternate spellings/padding before bounded decode. Authenticated plaintext key ID/
version must match wrapper/configuration. Do not trust wrapper for any identity beyond key lookup.

Before minting replayable state, enforce a prospective full-history request bound: all current
projected input items plus all completed output items plus one maximum-sized function result
per output call, root context/negotiation fields and repeated carriers must fit2MiB intake. Reserve
maximum configured max_result_bytes plus512bytes JSON framing per pending call. For text-only
turns reserve at least64KiB plus512bytes for a next user input. Count worst-case JSON escaping
(6bytes per string code point) for unprovided results rather than raw UTF8 bound alone; actual
next request must still obey ordinary intake/feature caps. Existing history+new items+pending
result count must fit max_history_items; distinct sealed turns including new turn<=16; combined
carrier occurrences<=512KiB. Add256bytes for next max_output_tokens/stream/metadata control;
metadata in signed v1 capped128bytes serialized. Media/tool/schema context and history bytes
count in wire projection; caller can choose smaller results but cannot rely on cap violations.

Sealing rejects the billable provider turn safely when prospective replay cannot fit; no completed
call/state or success terminal is emitted. This is a resource contract, not automatic truncation
or discarding earlier history. Generated state/output never bypasses input/body/history caps.
Large contexts/earliest expiry can require callers to start fresh; no server token renewal/cache.

Digest framing is exact: history SHA256 starts with ASCII `foundry-history-v1\0`; for each
canonical item append its UTF8 byte length as unsigned big-endian8bytes, then item JSON bytes.
Copy hash at the boundary after final item of each turn. Context SHA256 hashes ASCII
`foundry-context-v1\0` followed by8byte length and canonical context JSON. Native Part SHA256
hashes ASCII `foundry-part-v1\0` followed by8byte length and canonical unsigned Part JSON.
Publish synthetic vectors for zero/one/multiple items and adjacent text/call Parts; seal and
validate use one shared implementation. Length framing includes no array closing-bracket
ambiguity and incremental history hashing touches each projected byte once.

Initial signed pools require identical complete feature profiles across all members. Validate
common context once per request and reuse its digest; backend fingerprints remain distinct.
This avoids backend-count amplification of schema/tool serialization and keeps the reviewed
context-work bound. Arbitrary pool counts remain supported; heterogeneous signed contracts
require separate logical pools until a different bounded context algorithm is reviewed.

## OpenAI Python 2.8.1 helper serialization

The actual `responses.stream()` helper parses strict function arguments locally and adds a
`parsed_arguments` field to its completed function-call model. That field is not part of the
server wire item or authenticated history. Replay function calls using:

```python
item.model_dump(exclude_none=True, exclude={"parsed_arguments"})
```

For assistant messages use `item.model_dump(exclude_none=True)`. Preserve the exact emitted
arguments string, IDs, status and `foundry_provider_state`; do not regenerate arguments from
parsed objects. The router continues to reject unknown top-level `parsed_arguments`. This
serialization excludes the local helper field only; same-named nested schema/argument/result
fields are preserved. Synthetic HTTP tests cover both plain `responses.create` and streamed
strict-tool result replay using this explicit recipe. Default streamed helper dumps are rejected.
