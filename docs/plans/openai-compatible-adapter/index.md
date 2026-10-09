# Generic OpenAI-Compatible Adapter Extraction

## Companion Documents

- [Inputs](inputs.md)
- [Activities](activities.md)
- [Outputs](outputs.md)
- [Exit Criteria](exit-criteria.md)
- [Risk Register](risk-register.md)
- [Evidence](evidence.md)

## Status

**Implemented** (2026-10-08), with local verification recorded in [evidence](evidence.md).
Behavior-preserving refactor of the
[Google AI Studio adapter](../google-ai-studio-adapter/index.md); no new provider is enabled.

## Objective

Move the provider-neutral Responses ⇄ Chat Completions translation out of
`api/adapters/google_ai_studio.py` into a reusable `api/adapters/openai_compatible.py`
module. Google keeps only what is Google-specific: the feature profile, tool/schema/media
request context, call translation and vendor notes. A future OpenAI-compatible upstream can
then reuse the validated envelope, SSE, embeddings, usage and error logic without
inheriting Google's capability profile.

## In Scope

- `OpenAICompatibleAdapter`: Responses top-level validation, embeddings validation and
  translation, Chat Completions success translation, sanitized error mapping, usage extraction
  and Chat Completions request assembly (`max_completion_tokens`, `stream_options`).
- `OpenAICompatibleStreamDecoder`: bounded SSE framing, Responses lifecycle events, refusal and
  function-call delta assembly, terminal/failure events and usage absorption.
- Explicit hook methods for provider request context, feature permission, message building
  and call translation; a read-only `ChatRequestContext` protocol describing shared context
  members, with context-parameterized adapter/decoder bases preserving Google's concrete type.
- A provider label (`"Google"` for Google) so client-visible rejection messages stay identical.
- `GoogleAiStudioAdapter` and `GoogleStreamDecoder` become thin subclasses; existing
  `google_native`, `google_audio_output` and `google_signed*` subclasses keep working unchanged.
- Backward-compatible `MAX_GOOGLE_*` constant names re-exported from the Google module.
- Deterministic pre-extraction characterization fixtures for public rejection objects,
  upstream request bodies, translated responses and ordered SSE bytes.

## Out of Scope

- A new configurable `openai_compatible` provider value, endpoint or credential handling.
- Generalizing `google_tools`, `google_schema` or media helpers (they stay profile-bound).
- Making package imports transitively Google-free; `api/adapters/__init__.py` retains its
  existing provider imports. The generic module has no direct runtime Google dependency;
  the existing `PreparedGoogleMedia` annotation is the sole permitted type-only exception.
- Any change to forwarding, routing, quota, credit or wire behavior.

## Entry Criteria

- Clean tree at `043603b`; Google adapter suite green.
- Plan reviewed by an independent session.

## Exit Criteria

See [exit-criteria.md](exit-criteria.md).

## Roles

- Owner: implementing agent session
- Reviewer: independent review session
- Approver: repository maintainer
