# Tools and Multimodal Risk Register

## Risks

| ID | Risk | Impact | Mitigation | Status |
| --- | --- | --- | --- | --- |
| R1 | Predecessor plan mistaken for implemented foundation | Work targets nonexistent interfaces/safety guarantees | Require predecessor code gate and re-inspect interfaces before dependent implementation | Open |
| R2 | Responses client drops opaque signatures | Follow-up tool calls fail or lose provider context | Exact client replay tests, reviewed lossless carrier, disable affected capabilities on failure | Open |
| R3 | Continuation state forged/rebound or forwarded to another provider | Integrity failure, state disclosure or incorrect context | Authenticated encryption, caller/history/backend binding, expiry and pinned routing | Open |
| R4 | Key rotation or restart invalidates signed history | Conversations cannot continue | Document key retention/revocation and bounded state lifetime; test rotation/restart/drain | Open |
| R5 | Tool IDs/results or parallel deltas become interleaved incorrectly | Wrong function/result association | Ordered typed items, per-call bounded assembly, duplicate/orphan tests | Open |
| R6 | Partial arguments interpreted as completed executable calls | Caller acts on invalid model output | Completion only after argument/state validation, client execution-trigger tests | Open |
| R7 | Schema translation weakens constraints or validates without bounds | Incorrect strictness claims or CPU/memory exhaustion | Shared supported-keyword subset, bounded refs/work and local final validation | Open |
| R8 | Media URLs/schema refs create SSRF or unintended data forwarding | Arbitrary egress or credential disclosure | Inline-only media and no external reference resolution; zero-egress rejection tests | Open |
| R9 | Encoded/compressed media bypass memory or work limits | OOM, parser stalls, expired reservations | Layered wire/decoded/pixels/pages/duration/work limits; bounded parsers and concurrency measurements | Open |
| R10 | Base64/text prices stand in for multimodal accounting | Under-reserved credit or quota violations | Per-model conservative media bounds and explicit price/quota dimensions before enablement | Open |
| R11 | Features work separately but not together | Tool/image/schema requests silently degrade | Explicit combination profiles and combined fixture/live gates | Open |
| R12 | Native transport introduced as automatic fallback | Duplicate generation, incompatible signature replay | Explicit configured surface, separate fixtures and no automatic switching | Open |
| R13 | New media shapes misrepresented as standard Responses | Client breakage and unusable streams | Public-schema/extension decision before implementation; per-client output tests | Open |
| R14 | Schema/media failure after generation releases credit or retries | Multiple paid generations escape accounting | Preserve predecessor typed outcomes, ambiguous-dispatch termination and conservative settlement | Open |
| R15 | Tool content/signatures/media escape through exceptions or telemetry | Sensitive content exposure | Safe errors and synthetic marker tests across all diagnostic surfaces | Open |
| R16 | Broad compatibility claims outrun actual validation | Unsafe rollout or unsupported coding-agent workflows | Per-increment/model/client evidence and separate live/production gates | Open |
| R17 | Client drops continuation state and mixed pool selects an unsigned backend | Required signed history silently loses context/binding | Request-wide logical-pool history validation before candidate filtering; dropped-carrier tests with healthy alternatives | Open |

## Open Decisions

- **T1 / Increment A:** exact supported schema/tool combinations; signature requirements and
  carrier through the chosen client; any explicit extension schema, canonicalization, auth-scope
  derivation, encryption dependency and key/expiry policy. These block their dependent features.
- **T1/T5 / Increment B:** actual inline PDF/public form and transport support; safe parsers,
  dimensions/page limits, conservative token estimates and prices. Images and PDFs have separate gates.
- **T1/T6 / Increment C:** priorities and verified public forms for audio/video input and image/
  audio output, need for native transport, output framing, parser isolation and extra price/quota
  dimensions. No native/media implementation is assumed approved by a placeholder decision.
- **Before live tests:** operator-supplied model/client versions, project/credential topology and
  finite test ceilings. Missing live inputs do not block synthetic contract and code work.

Decisions already fixed: caller executes tools; inline media first; no arbitrary fetching,
uploads/conversation store or hosted tools; new profiles off by default; reuse owning boundaries;
do not weaken predecessor retry/accounting or production memory/one restrictions.
