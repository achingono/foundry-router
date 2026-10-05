# Google AI Studio Backends and Responses Adapter

## Companion Documents

- [Inputs](inputs.md)
- [Activities](activities.md)
- [Outputs](outputs.md)
- [Exit Criteria](exit-criteria.md)
- [Risk Register](risk-register.md)
- [Evidence](evidence.md)
- [Adapter contract](adapter-contract.md)

## Status

**Planned**. This is an implementation plan, prepared against commit `b6a188c` on
2026-10-05. Runtime implementation and real Google inference verification are pending.
It extends the [Phase 09 work](../phase-09-google-ai-studio-multikey/index.md).
Independent plan review is complete with no blocking findings remaining; see [Evidence](evidence.md).

## Objective

Make configured Google AI Studio backends usable through the router's existing Responses
and embeddings API. Add an explicit protocol adapter between Responses and Google's
OpenAI-compatible Chat Completions surface, including translated SSE events, usage,
errors, and operation-aware routing. Retain the existing asynchronous HTTP transport,
project-group quota controls, credit lifecycle, and Azure contracts.

## Inspected Baseline

| Area | Current status and evidence | Work required |
| --- | --- | --- |
| Google configuration and transport | **Implemented**: `google_ai_studio`, endpoint, credential, deployment/model substitution, URL mapping and header stripping in `config/` and `backends/` | Reuse; validate capabilities and provider operation contracts |
| Responses translation | **Partially implemented**: `_google_operation()` maps `responses` to `chat/completions`; `prepare_upstream_payload()` changes only `model` | Translate `input` to `messages` and Chat Completions output to Responses objects |
| Streaming translation | **Planned**: forwarding currently passes raw upstream bytes and inspects usage | Decode Google SSE and emit Responses lifecycle events with bounded state |
| Google quota routing | **Implemented** within Phase 09's single-process scope | Preserve project-group semantics and exercise real adapter requests |
| Embeddings quota integration | **Partially implemented**: embeddings route omits `rate_limit_store` from routing and finalization | Wire admission, failover and settlement for embeddings |
| Tests | **Implemented** for provider URL/auth and mocked routing | Replace permissive Google success fixtures with strict Chat Completions/embeddings contracts |
| Real Google inference | **Planned**; no such evidence was found in the inspected plans | Separate opt-in, bounded test-environment verification |

Source references and limitations are recorded in [Inputs](inputs.md). Existing Phase 09
evidence proves its recorded scope; it does not prove end-to-end Responses compatibility.

## In Scope

- Arbitrary configured Google backends using existing credentials and model pools, with
  explicit supported operations and capability filtering before reservation and failover.
- A first release supporting text Responses, stateless text message history, instructions,
  streaming, usage normalization, and text embeddings. The exact contract and rejected
  fields are defined in [Adapter contract](adapter-contract.md).
- A small provider adapter interface owned by `api/`, an Azure pass-through adapter, and
  a Google compatibility adapter. Backend credentials and URL enforcement stay in `backends/`.
- Safe protocol errors, cancellation cleanup, conservative settlement when usage is
  unavailable, and no retry after downstream SSE delivery begins.
- Focused tests, regression gates, synthetic configuration examples, canonical documentation
  and requirements traceability updates, followed by optional real-provider evidence.

## Out of Scope

- Gemini native `generateContent`, Vertex AI, Google OAuth/service accounts, public
  `/chat/completions`, dynamic provider model discovery, and Google infrastructure provisioning.
- Function tools, structured-output schemas, multimodal input/output, exposed reasoning,
  built-in tools, and opaque thought-signature round trips in the first release. These need
  follow-up contracts and client tests; unsupported requests must fail explicitly.
- Stored Responses, `previous_response_id`, Conversations, background jobs and WebSockets.
- Distributed quota accounting, per-model quota-store redesign, automatic key/project lookup,
  billing integration, mixed metered/free pools, and production rollout.

This first release is a text/embeddings compatibility subset. It must not be advertised as
full compatibility with coding-agent workflows that require function tools.

## Design and Sequence

1. Confirm the current Google compatibility contract, supported model IDs and authentication;
   pin synthetic fixtures and the support matrix before changing runtime behavior.
2. Add provider adapters and operation capabilities while preserving Azure regression contracts.
3. Implement non-streaming Responses and embeddings translation plus quota wiring.
4. Implement bounded SSE translation and lifecycle-safe settlement.
5. Complete security, retry, quota, credit and client-contract regressions; update docs.
6. Record code verification separately from opt-in real Google inference. Enable only verified
   capabilities in an isolated memory-backed, one-worker, one-replica test environment.

See [Activities](activities.md) for deliverables, dependencies, test commands and rollout gates.

## Entry Criteria

- The baseline and affected tests have been inspected; the initial working tree was clean.
- An independent session reviews this plan before implementation, as required by
  [AGENTS.md](../../../AGENTS.md). Record findings and dispositions in [Evidence](evidence.md).
- Vendor contract questions in [Inputs](inputs.md) are resolved before the dependent code
  is implemented. Runtime work requires no real credentials.
- Real-provider tests require separately supplied test-only credentials, actual model IDs,
  project grouping, applicable quotas, and a request/spend bound.

## Exit Criteria

See [Exit Criteria](exit-criteria.md). Code completion and live validation are separate gates.
Production remains memory-backed with `maxReplicas: 1` under the existing cut-over policy.

## Roles

- Owner: Implementation contributor.
- Reviewer: Independent planning session, then independent deep review of implementation.
- Approver: Project maintainer for release decisions; this plan does not record release approval.
