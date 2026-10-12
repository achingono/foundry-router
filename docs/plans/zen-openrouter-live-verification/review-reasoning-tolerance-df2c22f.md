# Independent reasoning-tolerance review of df2c22f

Date: 2026-10-11.
Reviewed commit: `df2c22f5ae55a99cef01dcc0ceb3438d1a79c997`.

Scope: all thirteen changed files, adapter selection and shared Chat translation,
Google normalization inheritance, forwarding rejection/settlement paths,
logging/redaction, the amendment and canonical API/configuration/security docs,
and relevant tests. The reviewing assistant independently reviewed the completed
implementation in this session. Only review/status documentation was edited.

## Disposition

**Independent amendment review gate cleared for the local implementation.**
No Critical or Major findings were identified in the reviewed runtime paths.
Two non-blocking Suggestions are recorded below. This does not establish live
provider compatibility or authorize reusing any halted ledger. Live reruns need
new reviewed run identities and their normal dispatch/evidence gates.

## Verified behavior

- Only `CompatibleTextAdapter` and its stream decoder opt into the `reasoning`
  allowance; registry use covers generic compatible and OpenRouter providers.
  The shared base remains strict by default. Google-specific files were not
  changed, and the existing compatibility characterization suite passed.
- The allowance is precisely `None` or the empty string, not arbitrary false-like
  values. The translator rebuilds public responses/events from known fields,
  so the tolerated field is omitted. Content-bearing reasoning and other unknown
  fields still reject before being emitted as public content.
- Independent adapter probes fixed generated IDs/time and compared absent,
  null and empty reasoning: non-streaming public bodies and completed streaming
  bytes were identical, including when input SSE arrived in three-byte fragments.
  Nonempty text, whitespace, zero, false, empty list and empty object were rejected.
  Google still rejected null and empty reasoning.
- The forwarding changes add debug logging in the existing ValueError catches;
  they do not alter retry eligibility, settlement inputs, cooldowns or public
  error construction. Current catches handle the new exception directly. Existing
  streaming settlement and provider integration checks passed.
- The actual producer sanitizes field names before creating the exception; the
  new trace does not include provider field values or bodies. The diagnostic
  precision and exception interoperability limits below remain worth correcting.

## Suggestions

### RT-1 — Suggestion: Keep the placeholder inside the eight-entry budget

- **File/Module:** [Rejection field sanitizer](../../../src/foundry_router/api/adapters/openai_compatible.py),
  `_rejection_fields` and `_check_output_fields`.
- **The Issue:** The helper takes eight safe names and then appends a placeholder
  on overflow, producing nine entries despite the amendment's eight-entry cap.
  It also derives the diagnostic list from all extra keys rather than the computed
  blocking keys, so tolerated null `reasoning` may be listed beside an actually
  rejected field.
- **Why Static Analysis Missed It:** This is a mismatch with the amendment's
  diagnostic contract; the list operations and bounded allocation are valid.
- **Impact:** The trace exceeds its stated count by one and can misidentify a
  tolerated field as the reason for rejection. It remains bounded and does not
  change admission, public errors or credit settlement.
- **Recommended Fix:** Reserve a slot for the placeholder within the eight-entry
  total and build the diagnostic from `blocking`. Add overflow and tolerated-key
  plus rejected-key cases.
- **Evidence:** An independent call with nine safe unknown keys returned nine
  entries (eight names and the placeholder).
- **Disposition:** Non-blocking suggestion; no implementation change made here.

### RT-2 — Suggestion: Preserve standard exception traceback mutability

- **File/Module:** [TranslatedRejectionError](../../../src/foundry_router/api/adapters/base.py).
- **The Issue:** `@dataclass(frozen=True)` blocks assignment to exception metadata
  such as `__traceback__`. Python generator context managers restore that metadata
  when propagating an exception, so this class is not fully interchangeable with
  a normal ValueError in such contexts.
- **Why Static Analysis Missed It:** Subclass/type checks pass; the difference is
  in runtime interaction with standard context-manager exception handling.
- **Impact:** A consumer allowing this exception to cross a generator context
  manager can receive `FrozenInstanceError` instead. The current reviewed
  forwarding sites catch the error locally and did not exhibit this failure;
  it is not a demonstrated current public-route or settlement regression.
- **Recommended Fix:** Use a normal ValueError subclass with a tuple of diagnostic
  fields, or otherwise leave BaseException metadata mutable. Retain controlled
  field construction and add synchronous/asynchronous context-manager propagation
  tests alongside the subclass check.
- **Evidence:** Raising the new exception inside a trivial `@contextmanager`
  scope produced `FrozenInstanceError`, rather than TranslatedRejectionError.
- **Disposition:** Non-blocking interoperability suggestion; no implementation
  change made here.

## Verification and limits

- 24 focused reasoning-tolerance/Zen/OpenRouter integration tests passed.
- 111 additional characterization, generic-provider, shared-decoder, Google
  integration, forwarding-stream and streaming-settlement tests passed.
- Independent offline probes verified absent/null/empty equivalence, fragmented
  SSE behavior, the rejection matrix and the two Suggestions above.
- Full-suite coverage, Ruff/mypy and Docker were not rerun by this reviewer;
  reported implementation checks are not represented as independent review runs.
  No SonarQube scan was performed; the conditional repository script is absent.
- Plan relative links, whitespace and the final documentation diff were checked.
  No runtime code/tests, credentials, production configuration or historical
  ledgers were modified. No live requests or reruns were sent.
