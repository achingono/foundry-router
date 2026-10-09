# Configurable OpenAI-compatible provider

**Implemented** locally, 2026-10-08. Live upstream compatibility remains unverified. Workstream-7 contract following the completed
[adapter extraction](../openai-compatible-adapter/index.md).

## Companion documents

- [Inputs](inputs.md)
- [Activities](activities.md)
- [Outputs](outputs.md)
- [Exit criteria](exit-criteria.md)
- [Risk register](risk-register.md)
- [Evidence](evidence.md)

## Objective and contract

Allow arbitrary configured non-Google upstreams exposing Chat Completions and embeddings
to serve logical Responses/embedding pools through `provider: openai_compatible`.
Reuse bounded translation and accounting with explicit capability and trust boundaries.

1. Admit the provider in BackendConfig. Endpoint is the exact configured HTTPS API root,
   including a required version path such as `/v1`. Append only `/chat/completions` for
   Responses or `/embeddings`; no Google/Azure suffix or query version. Reject operation
   paths, userinfo, queries, fragments and unsafe path segments. Validate the raw endpoint
   before HttpUrl normalization so dot segments and encoded path separators cannot disappear
   into a different allowed root. Require a bounded nonblank physical model identifier;
   generic model IDs are body-only and may contain namespace slashes (for example
   `organization/model`). Retain Azure/Google path-segment restrictions for those providers.
   Default operation is Responses; embeddings is explicitly declared.
   Native surface and nondefault Google profiles are invalid.
2. Credential remains externally supplied. Strip caller auth/cookies/forwarding headers
   and inject server `Authorization: Bearer` only. Preserve exact origin, port and base-path
   confinement and disabled redirects. Custom auth/header/query extensions are out of scope.
3. A provider-independent text context supplies the generic adapter hooks. Support string
   input and bounded text-only system/developer/user/assistant histories, instructions,
   metadata and existing generation parameters. Reject tools, structured-output extensions,
   images/files/audio/video, provider state and stored continuation before admission.
   Later feature additions need explicit provider capabilities and separate verification.
4. Generic Responses use bounded translated nonstreaming/SSE forwarding. Confine Google
   native/media helpers to Google branches. Select adapters using the actual configured
   provider; generic failures must not select a hard-coded Google adapter. Share only the
   transport paths actually required by this provider, preserving existing Google callers.
   The supported fixed wire dialect sends `max_completion_tokens` and
   `stream_options.include_usage`; upstreams requiring alternate parameters need a separate
   explicit dialect extension. Compatibility is verified per upstream/model.
5. Single-shot attempts; only pre-output 429 permits routing failover; no retry after any
   downstream event. Ambiguous dispatched 5xx/transport/protocol failures retain known usage
   or full estimates. Auth failures do not cycle credentials. Quota and credit remain separate;
   existing quota/credit groups apply without Google-derived balances.
6. Logical models and aliases determine pools, with arbitrary backend counts, mixed
   Azure/Google/generic text pools and operation filtering. No infrastructure or production
   change, and no live upstream availability claim in this implementation phase.

Independent model/session review cleared this concrete plan before runtime changes; a separate contextual implementation review found no Critical/Major issues.
Local tests, strict typing, coverage, Docker and contextual review establish implemented
code. Actual upstream/model/client compatibility remains a separate live gate.
