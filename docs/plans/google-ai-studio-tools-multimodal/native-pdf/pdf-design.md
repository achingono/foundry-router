# Bounded PDF preparation contract

**Planned**, drafted2026-10-05 for separate independent review before parser/runtime edits.
Native foundation review passed; this contract closes its preliminary PDF design only.

## Public input and exact admission

Responses user content accepts `input_file` with exactly type/file_data/filename. file_data
must be `data:application/pdf;base64,` and canonical validated base64. filename is1–64 ASCII
letters/digits/dot/underscore/hyphen, ending `.pdf`; no path/URL/file ID. Native forwards only
the original bytes as inlineData; filename is display metadata and never a path or prompt.
Document acceptance requires default-off `inline_pdfs`, exact combination permission, native
surface and explicitly affirmed document input-token pricing/ceiling. Limits:64KiB/document,
128KiB aggregate,4 documents,4 pages aggregate. Page dimensions<=14400 PDF points, finite,
positive, with bounded page-tree inheritance. No external retrieval or rendering.

## Parser boundary and resource isolation

Pin pypdf6.19.0, current PyPI release verified2026-10-05; downloaded wheel for API/source
review, not installed yet. Inspect reader/generic APIs and strict-mode repair behavior before code.
Source inspection found `PdfReader.get_object` repairs mismatched offsets even in strict mode.
Therefore independently parse the finite classic xref and verify every exact declared offset,
object number/generation, stream raw length and object terminator before calling reader APIs;
reject any warning/repair and changed xref state. Run these checks before constructing PdfReader:
strict reader can rebuild malformed xref and decode object streams during rebuild. Independently
check exact stream spans: generic reader may trim an overlong stream length even in strict mode.
Strict=True alone is insufficient evidence.
Invoke a repository-owned worker via current Python executable and `-m`, never a caller path.
Worker module imports only stdlib before limits; pypdf imports after limits. Invoke isolated
Python mode, a minimal allowlisted environment and repository-owned module, with no inherited
credentials/provider configuration. Worker receives raw bytes on stdin, sets POSIX RLIMIT_CPU=2seconds, RLIMIT_AS=256MiB,
RLIMIT_FSIZE=0, RLIMIT_NOFILE=32 before parser invocation and emits at most1KiB JSON metadata.
No file output, stderr content, network calls, subprocess invocation or document-directed external
I/O. pypdf import reads reviewed dependencies, probes optional crypto/Pillow imports and calls
shutil.which('jbig2dec') in configuration defaults. Empty owned PATH prevents executable discovery;
never invoke get_data/render/extract or optional codecs. This import behavior must be measured.
POSIX resource limits bound work and are not a filesystem/network sandbox: source-reviewed
parser path issues no external I/O; stronger OS sandboxing remains separate if parser code changes.
Parent disables stderr, writes bounded stdin and reads stdout incrementally with a hard1025byte
overflow sentinel; do not use unbounded communicate() accumulation. Enforce2second wall timeout
and original intake deadline, kills and reaps on timeout/cancellation/invalid output. Unsupported
resource-limit platforms or absent dependency fail PDF readiness, leaving other features usable.
Implementation experiment: macOS27/Python3.14 rejects RLIMIT_AS setup, so enforced PDF readiness
is currently Linux-only. Pinned dependency and a cached isolated owned-fixture self-test verify
actual limit/import/parser availability; runtime infrastructure failure is503, document rejection422.

Initial finite PDF grammar: classic xref/trailer only; reject encryption, object/xref streams,
compression/filter dictionaries, external stream files, actions/annotations/scripts/forms,
embedded files, XObjects/images/fonts requiring external data and incremental revisions.
Strict reader plus lexical container checks; cap256 indirect objects,2048 visited nodes,
reference depth16 and4 pages. Traverse every indirect object, not only reachable page objects;
reject unresolved references, arbitrary cycles, forbidden dictionary keys, exotic objects and streams
outside declared raw length. Stream/string bytes are counted toward64KiB and node work limits.
Validate exact EOF and xref entry/object consistency rather than tolerating repairs. Parser must
not extract text, render, decode compressed data or normalize/rewrite document bytes.

Allow only verified page-tree `/Parent` backedges: walk `/Kids` top-down, require unique node
ownership and exact child `/Parent` identity, verify `/Count` against descendant pages, bound
inheritance/depth, and exclude that checked backedge from generic cycle detection. Other cyclic
graphs and duplicate/shared page nodes reject. Streams may be referenced once globally and once
in one page's `/Contents`; repeated content references reject. Font dictionaries permit only
standard14 built-in Type1 fonts with standard encoding; reject ToUnicode/custom encoding maps,
Type3/composite/embedded font programs and custom glyph expansion. Restrict text strings in page
content to single-use standard encoding under a separately reviewed bounded content grammar.
Content operator allowlist: BT/ET, Tf, Tj/TJ, Td/TD/Tm/T*, Tc/Tw/Tz/TL/Ts/Tr and basic g/rg/k
color setters only, with exact arity/type checks and balanced text objects; reject all other
operators including BI/ID/EI, Do, gs and marked content. Standard font references must resolve
to verified resources, text strings each<=16KiB, total<=64KiB, arrays<=256 elements and operators
<=2048. Numeric operands must be finite with absolute value<=14400; font size in(0,1000], scale
in(0,1000], rendering mode integer0–7. Reject /UserUnit, transformations/graphics resources outside
this grammar and all nonfinite page geometry. Tokenize bounded raw content before any pypdf
ContentStream/inline-image parser; no decoder runs for rejected operators. Require direct integer
stream /Length<=64KiB and exact raw span validation before the dependency sees document bytes.

Parser dependency/version-specific traversal and accepted grammar require strict fixtures and
independent review; the above limits are targets until Linux/macOS measurements prove them.

## Owned immutable preparation and lifecycle

API prepares PDF metadata once after authentication/model alias resolution, before any routing
reservation. Use a frozen `PreparedGoogleMedia` value, with frozen tuple of PDF entries containing
content position, SHA256 digest of exact encoded data, decoded byte count and page count.
Explicit optional `prepared_media` keyword flows through adapter check/build, routing selection
and failover, and forwarding build. No dictionary key/body subclass/ContextVar/global media cache.
Adaption checks entry position/digest and its own lower caps; absent/mismatched metadata rejects.
Caller-provided fields cannot construct the owned object; no counts are accepted from JSON.
Prepared values contain no prompts/filenames/media and are never serialized or logged.

An API-owned preparer has at most2 active worker slots per process and no waiting queue: atomically
check/increment with no await between them; saturated
PDF intake returns bounded503 before reservation. Acquire slot before decoding/spawn. Process
PDFs sequentially within a request; release slot in finally after child reap. At most2 PDFs parse
concurrently across requests. Original intake deadline covers decode/worker/metadata and admission.
No worker on selection/build/failover; adapters only compare immutable prepared facts/digests.
Authentication/body/global2MiB cap and finite content/history counts run before parsing. Search
only the selected model's configured PDF-capable profiles; no enabled profile means pre-egress422.

## Conservative quota/credit accounting

Require operator `pdf_input_tokens_per_page>=258`, `pdf_native_text_tokens_per_page` with an
explicit finite model-specific upper-bound affirmation, and `pdf_token_pricing=true` per profile;
derive server-owned pool maximum. Reserve per document:
`(configured_visual_per_page + configured_native_text_per_page) * configured_max_pages + decoded_document_bytes + 64`.
Use full configured page maximum for each document instead of caller counts; UTF-8 native text
budget includes all uncompressed document bytes plus the affirmed native-text page ceiling.
Decoded bytes alone are not evidence of a native-text token upper bound. Parser forbids repeated
streams/font expansion, and measured finite content grammar plus exact model evidence must
justify the text ceiling before enablement. Caller cannot reduce
estimation by changing page metadata. Other text/tool/schema/history framing estimates remain.
This deliberately exceeds actual parsed page count; exact actual native usage settles billing.
Missing/invalid usage charges the full reservation. Nonmetered projects retain zero dollar pricing
and conservative token/quota admission. Require Google-native-only logical pools for PDF profiles.
Current vendor document says258/page and distinct Gemini3 native-text billing; exact operator
model/price/quota affirmation and live evidence remain mandatory. Do not infer model support.

## Verification

Deterministic tiny valid1/4-page PDFs and misleading MIME/base64/page count, encryption,
compressed streams, object/xref streams, external actions, malformed xref/EOF/length/reference
trees and cycles. Preserve text/PDF/image order, tools/schema combinations and SDK continuation.
Test no profile/missing metadata/mismatched digest/lower candidate caps before reservation;
three-project selection/failover and nonmetered token estimates. Test worker saturation,
timeout/cancellation/reap/dependency/readiness, known/missing usage and independent cleanup.
Measure actual API preparation→selection→build→encoding at8 callers, including maximum valid,
late-invalid and mixed media workloads. Gate incremental RSS<=128MiB, loop delay<=1second,
worker CPU/wall limits and intake<5seconds. Sample simultaneously live parent plus all children
RSS and container peak (RUSAGE_SELF alone is insufficient); rlimits AS do not establish RSS caps.
Total peak must remain within the configured512MiB container and incremental aggregate peak
within128MiB. Adjust worker count/AS ceilings downward if measurements fail before enablement.
Separate Python3.12 Linux container and local
measurements. Full suite/coverage>=80%, Ruff/mypy/Docker, independent deep review and links.
