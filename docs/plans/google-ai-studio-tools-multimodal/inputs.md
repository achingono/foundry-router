# Tools and Multimodal Inputs

## Required Inputs

| Input | Source | Owner |
|---|---|---|
| Predecessor plan and safety decisions | [Adapter plan](../google-ai-studio-adapter/index.md), [contract](../google-ai-studio-adapter/adapter-contract.md), [review evidence](../google-ai-studio-adapter/evidence.md) | Runtime contributor |
| Implemented predecessor interfaces | Future code-gate evidence; the plan commit `d3a6dec` is not implementation evidence | Runtime contributor |
| Owning boundaries/public contracts | [Architecture](../../architecture/index.md), [API](../../api/index.md), [configuration](../../configuration/index.md), [security](../../configuration/security.md), [routing](../../features/routing.md) | Adapter contributor |
| Current source baseline | [Config](../../../src/foundry_router/config/__init__.py), [backend client](../../../src/foundry_router/backends/__init__.py), [API validation](../../../src/foundry_router/api/common.py), [credit estimates](../../../src/foundry_router/credit.py), [forwarding](../../../src/foundry_router/forwarding/__init__.py) | Runtime contributor |
| Existing regressions | [API tests](../../../tests/unit/test_api_common.py), [backend tests](../../../tests/unit/test_backends.py), [credit tests](../../../tests/unit/test_credit.py), [stream tests](../../../tests/unit/test_forwarding_stream.py), [integration](../../../tests/integration/test_full_flow.py) | Test contributor |
| Safety and quality gates | [Testing](../../development/testing.md), [CI](../../../.github/workflows/ci.yml), [credit operations](../../operations/shared-resource-credit.md), [deep-review prompt](../../../.agents/prompts/deep-review.prompt.md) | Reviewer |
| Provider/model feature matrix and prices | Dated vendor sources below plus operator-selected models; no model support inferred from names | Adapter contributor/operator |
| Public-client behavior | Pinned Responses client version, request serialization and output-item history replay tests | Client integration contributor |

## Vendor and Client Confirmation (T1)

- [Google OpenAI compatibility](https://ai.google.dev/gemini-api/docs/openai): exact supported
  tool, schema, media and provider-extension fields; streaming shapes and usage details.
- [Function calling](https://ai.google.dev/gemini-api/docs/function-calling) and
  [thought signatures](https://ai.google.dev/gemini-api/docs/thought-signatures): when signatures
  are required, their scope/association, preservation rules, parallel calls and stream timing.
- [Structured output](https://ai.google.dev/gemini-api/docs/structured-output): supported JSON
  schema keywords, strictness, safety outcomes, tool/schema combinations and model constraints.
- [Image understanding](https://ai.google.dev/gemini-api/docs/image-understanding),
  [document processing](https://ai.google.dev/gemini-api/docs/document-processing),
  [audio understanding](https://ai.google.dev/gemini-api/docs/audio),
  [video understanding](https://ai.google.dev/gemini-api/docs/video-understanding),
  [image generation](https://ai.google.dev/gemini-api/docs/image-generation), and
  [speech generation](https://ai.google.dev/gemini-api/docs/speech-generation): precise
  media types, supported operations/models, inline limits, safety and output contracts.
- [Token counting](https://ai.google.dev/gemini-api/docs/tokens),
  [pricing](https://ai.google.dev/gemini-api/docs/pricing), and
  [rate limits](https://ai.google.dev/gemini-api/docs/rate-limits): media token/cost dimensions,
  reasoning/cache semantics, model quotas and bounded count-token alternatives.
- [Responses reference](https://platform.openai.com/docs/api-reference/responses) and
  [streaming events](https://platform.openai.com/docs/api-reference/responses-streaming):
  legal tool/media items and event sequences. Check actual pinned client serializers; do not
  equate a permissive JSON parser with retained provider-state support.

These URLs are research inputs, not evidence that the pages or features were verified during
drafting. Record current canonical URLs, dates and conclusions in T1. If a public schema or
lossless carrier is absent, keep that capability disabled and record the API decision required.

## Baseline Constraints

- The current `BackendConfig` has no per-feature/media capabilities or API-surface selector.
  Even `supported_operations` belongs to the unimplemented predecessor plan.
- Current Responses input validation is broad; nested media/tool safety is not established.
- Credit estimation walks text under `input` and uses one logical-model input/output price.
  Base64 size, image pixels, PDF pages, durations, tool declarations and generated media units
  are not a modality-aware admission model.
- Client authentication currently verifies keys without exposing a stable principal to the
  adapter. Any caller-bound continuation extension needs a deliberate internal identity change.
- The 2 MiB request-body default and existing stream/credit lifetime limits remain the starting
  bounds; increasing them requires measured memory/concurrency evidence.

## Optional Inputs

- Operator priorities among audio/video input and image/audio output for Increment C.
- A target coding-agent/client version with known function-result and unknown-field behavior.
- Tiny synthetic media fixtures and local mock-tool outputs with no sensitive content.
- Live-only model IDs, credential references, project groups and request/token/spend ceilings.

## Input Validation Checklist

- [x] Current tree, canonical docs, predecessor plan and relevant source/tests inspected.
- [x] Independent draft review complete and findings addressed.
- [ ] Predecessor implementation code gate passed before dependent runtime edits.
- [ ] T1 provider/client/schema/signature matrix confirmed before enabling capabilities.
- [ ] Media parser/estimator bounds and prices confirmed per modality.
- [ ] Live-only operator inputs supplied before real calls.
