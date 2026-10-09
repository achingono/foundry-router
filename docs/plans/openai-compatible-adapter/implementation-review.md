# Adapter extraction implementation review

Reviewed 2026-10-08 by the implementation session using
[the repository deep-review prompt](../../../.agents/prompts/deep-review.prompt.md).
The plan had prior independent session review; this implementation review is not claimed
as a separate independent review. SonarQube script is absent.

## Major finding addressed: incomplete provider-label extraction

- **File/Module:** `api/adapters/openai_compatible.py` rejection and finish-reason paths.
- **The Issue:** Four pre-existing f-strings retained the literal Google label after the
  initial move. A future subclass would return the wrong provider name.
- **Why Static Analysis Missed It:** Valid string literals do not violate syntax or typing;
  their correctness depends on the new provider abstraction.
- **Impact:** Incorrect client rejection and diagnostic messages for reused adapters.
- **Recommended Fix:** Use `self.provider_label` in every such path. Applied; focused tests
  cover unknown request fields and unknown nonstreaming/streaming finish reasons. The
  unchanged Google characterization oracle passes.

## Architectural and lifecycle checks

The generic module imports no Google runtime code, profile, transport, routing, credential,
quota or credit store. The sole Google annotation import remains under `TYPE_CHECKING`.
All four adapter hooks and the decoder call hook fail closed. Context remains request-local;
concrete Google typing preserves native argument validation. Per-request SSE state, bounds,
sequence and terminal handling remain in the inherited decoder; no slots or new global
conversation state were introduced. Google decoder default context and explicit creation
context are preserved. Existing prefetch EOF handling, signed delivery and audio adapter
paths remain unchanged.

Twenty-four core methods matched the original AST after normalizing only provider labels,
constant/type names and the call-validation hook. The changed context/permission/message
and decoder-construction methods were inspected separately against the original flow.
Full deterministic responses/SSE bytes and usage fields match the pre-extraction oracle;
existing native, signed, audio, cancellation and settlement regressions pass. No remaining
Critical or Major issue identified within this extraction's scope.
