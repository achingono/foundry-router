# Google AI Studio Adapter Inputs

## Required Inputs

| Input | Source | Owner |
|---|---|---|
| Boundaries and public behavior | [Architecture](../../architecture/index.md), [API](../../api/index.md), [routing](../../features/routing.md) | Runtime contributor |
| Provider and metering configuration | [Configuration](../../configuration/index.md), [security](../../configuration/security.md), [ADR-007](../../decisions/adr/007-provider-aware-quota-routing.md) | Runtime contributor |
| Previous Google scope and evidence | [Phase 09 plan](../phase-09-google-ai-studio-multikey/index.md), [evidence](../phase-09-google-ai-studio-multikey/evidence.md) | Runtime contributor |
| Transport and route implementation | [Backend client](../../../src/foundry_router/backends/__init__.py), [routes](../../../src/foundry_router/api/routes/openai.py), [forwarding](../../../src/foundry_router/forwarding/__init__.py) | Adapter contributor |
| Admission and settlement | [Routing](../../../src/foundry_router/routing/__init__.py), [credit](../../../src/foundry_router/credit.py), [quota](../../../src/foundry_router/ratelimit.py), [API common](../../../src/foundry_router/api/common.py), [cleanup](../../../src/foundry_router/cleanup.py) | Runtime contributor |
| Existing test contracts | [Backend tests](../../../tests/unit/test_backends.py), [stream tests](../../../tests/unit/test_forwarding_stream.py), [integration tests](../../../tests/integration/test_full_flow.py), [quota tests](../../../tests/unit/test_ratelimit.py) | Test contributor |
| Quality and operational requirements | [Testing](../../development/testing.md), [CI](../../../.github/workflows/ci.yml), [operations](../../operations/index.md), [credit recovery](../../operations/shared-resource-credit.md), [deep review](../../../.agents/prompts/deep-review.prompt.md) | Reviewer |
| Current vendor contract | Vendor references below; dated confirmation required in W1 | Adapter contributor |
| Test topology for live validation only | Operator-supplied model IDs, credential references, project groups, limits and budget | Operator |

## Vendor Contract References and Confirmation Tasks

- [Google OpenAI compatibility](https://ai.google.dev/gemini-api/docs/openai): confirm base
  path, supported Chat Completions/embeddings fields, model support, authentication header,
  streaming usage options and terminal behavior.
- [Google rate limits](https://ai.google.dev/gemini-api/docs/rate-limits): confirm applicable
  project/model/tier limits, input-token semantics and reset windows. Do not infer quota from
  the number of keys or copy illustrative limits into a live configuration.
- [Google troubleshooting](https://ai.google.dev/gemini-api/docs/troubleshooting): confirm
  authentication, quota, overload, safety and malformed-request responses.
- [Responses reference](https://platform.openai.com/docs/api-reference/responses) and
  [streaming events](https://platform.openai.com/docs/api-reference/responses-streaming):
  pin the supported response fields, event ordering and terminal schemas in fixtures.

These are implementation inputs, not a claim that current vendor pages or any provider
endpoint were verified during planning. If a required assumption fails, amend the contract
and obtain another independent review before dependent implementation.

## Baseline Limitations to Account For

- The Google integration fixture returns a response ID and usage without a real
  `choices[].message` envelope, and does not require `messages` in the outbound request.
- The streaming reader commits after the first nonempty raw transport chunk. A translator
  needs complete SSE events and must distinguish upstream framing from downstream delivery.
- The current request estimate reads Responses `input`, but not `instructions`; translated
  instructions and message overhead must enter conservative admission estimates.
- Quota limits are keyed only by `quota_group`. A single shared project group can conservatively
  combine several models; it does not model distinct provider model buckets. Do not split
  same-project keys into separate groups to manufacture capacity.

## Optional Inputs

- A representative text-only client and pinned client version for an offline contract check.
- Sanitized real response shapes may inform synthetic fixtures; retained evidence must contain
  no prompts, output text, credentials, provider resource IDs or credential-bearing URLs.

## Input Validation Checklist

- [x] Current repository, canonical docs and affected tests inspected at `b6a188c`.
- [ ] Vendor contract and first-release field/event matrix confirmed in W1.
- [x] Independent plan review completed and findings addressed.
- [ ] Test-only topology and bounds supplied before W7 live verification.
