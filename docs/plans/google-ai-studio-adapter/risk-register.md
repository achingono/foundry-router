# Google AI Studio Adapter Risk Register

## Risks

| ID | Risk | Impact | Mitigation | Status |
| --- | --- | --- | --- | --- |
| R1 | Route substitution mistaken for protocol compatibility | Real Responses requests fail despite green permissive mocks | Strict provider request/response fixtures, SDK/event contracts and separate live evidence | Open |
| R2 | Silent loss of Responses features | Wrong answers or broken client history/tools | Explicit nested allow-list, supported subset and pre-egress capability errors | Open |
| R3 | Incorrect SSE commitment or terminal handling | Duplicate generation, malformed streams, missed usage | First-downstream-event latch, late-usage parsing, finite state machine and fragmented fixtures | Open |
| R4 | Successful generation followed by adapter failure releases credit | Under-accounted spend and repeat billable calls | Typed outcome retaining usage/billable state, conservative settlement and terminal protocol errors | Open |
| R5 | Embeddings or retries bypass quota admission | Unexpected 429s; repeated keys overstate capacity | Wire embeddings store, charge/admit attempts and test same-project groups | Open |
| R6 | Instructions/overhead or default output limit exceed reservation | Unsafe estimates and quota headroom | Include all supported input, enforce the reserved output limit and reconcile actual usage | Open |
| R7 | Unbounded provider events/final-output assembly | Memory exhaustion or leaked generation | Body/event/output/time bounds, backpressure and shielded independent cleanup | Open |
| R8 | Provider auth/schema/model behavior changes | Backend failures or false compatibility claims | W1 dated vendor verification, explicit models/capabilities, isolated live test gate | Open |
| R9 | Backend credentials or user content escape via errors | Secret or content disclosure | Structured safe errors, redacted diagnostics and synthetic marker assertions | Open |
| R10 | Adapter integration changes Azure behavior | Existing inference and stream regressions | Azure identity adapter and existing wire/credit regression suite | Open |
| R11 | Project-only quota groups combine model limits | Conservative underutilization or misconfigured admission | One project group with conservative operator limits; separate model-bucket redesign later | Open |
| R12 | Operations defaults misclassify existing Google embedding entries | New validation rejects a previously attempted operation | Document explicit embeddings migration and test defaults; no unsupported auto-discovery | Open |
| R13 | Text subset advertised to tool-dependent clients | Coding-agent requests fail at runtime | Publish capability table and explicit tool rejection; separate function/signature follow-up | Open |
| R14 | Ambiguous dispatched failure retried with only one credit reserve | Multiple billable generations exceed reserved credit | No Google retry/failover after ambiguous dispatch; settle known usage or estimate and retain quota | Open |
| R15 | Invalid highest-ranked key repeatedly selected | Healthy keys starved on subsequent requests | Backend-local bounded auth cooldown and repeated-request/expiry tests | Open |

## Open Decisions

- **Before dependent implementation (W1):** confirm compatibility authentication, token-limit
  field, streaming usage/terminator behavior, refusal mapping, embedding batch quota semantics,
  dimensions support and Responses required fields. Amend/re-review the plan if assumptions fail.
- **Before live verification only:** operator chooses actual models, project/credential mapping,
  free/paid tier, limits and test budget. Missing live inputs do not block mocked implementation.
- **Future scope:** function tools/signatures, structured outputs, multimodal/native Gemini,
  per-model quota buckets and distributed accounting each need separate contracts and evidence.

Decisions already made for this plan: use the existing compatibility transport, retain configured
model discovery, reuse quota/credit stores, and ship an explicitly bounded text/embeddings subset.
