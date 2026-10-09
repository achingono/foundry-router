# Configuration

## Status: Implemented (Google AI Studio quota-aware routing is single-process and the Responses/embeddings adapter is implemented with mocked verification; distributed quota accounting and real Google inference remain Planned)

Configuration is externalized through validated environment variables and dotenv values. Secrets must come from environment variables, Azure Container Apps secrets, or managed identity where supported. They must never be committed to source, Git history, images, logs, or diagnostic responses. Retry/cooldown/failover settings are runtime behavior, and Phase 04 local credit estimation settings are runtime-enforced.

## Backend and Model Pools

The configuration must support an arbitrary number of backends and an independent backend pool per model. A backend should identify subscription, project, region, endpoint, and deployment even if the first release uses only two subscriptions. Forwarding-capable backends require a deployment identifier.

`provider: openai_compatible` is **Implemented with mocked verification** for configured
Chat Completions/embedding upstreams. Supply the exact HTTPS API root in `endpoint`
(for example `https://compatible.example.test/v1`), an external `credential`, and the
physical model ID in `deployment`; namespaced body values such as `organization/model`
are allowed up to 512 UTF-8 bytes. Responses appends `/chat/completions`, and explicitly
declared embeddings appends `/embeddings`. No Azure/Google suffix or API-version query is
added. Encoded/dot/duplicate path segments, operation URLs, userinfo, queries and fragments
are rejected. Default operations are `["responses"]`; use `supported_operations` for
embeddings. Native surface and Google feature profiles are invalid for this provider.

The fixed dialect sends `max_completion_tokens` and `stream_options.include_usage`.
Text-only histories allow at most 128 messages, 128 text parts per message and 256 KiB
aggregate text including instructions. Tools, structured-output profiles, media, stored
continuation and provider state are rejected before admission. Configure quota groups,
credit metering and model prices independently; exact upstream/model live compatibility
remains unverified. See [provider contract](../plans/openai-compatible-provider/index.md).

```yaml
backends:
  sub_a:
    endpoint: ${FOUNDRY_A_ENDPOINT}
    credential: ${FOUNDRY_A_CREDENTIAL}
models:
  gpt-5.4:
    backends:
      sub_a: {weight: 1}
```

The initial logical model set is `gpt-5.6-luna`, `gpt-5.4`, `gpt-5.4-mini`, `gpt-5.4-nano`, `gpt-5.3-codex`, `gpt-5.2-chat`, and `text-embedding-3-large`.

## Logical Model Aliases (Implemented with mocked verification)

`FOUNDRY_MODEL_ALIASES_JSON` is an optional object mapping explicit client-facing alias
names to canonical model IDs (for example `{"codex-auto-review": "gpt-6.1-sol"}`).
It defaults to `{}` and creates no new capacity, pools, prices, or resources.
Resolution is exact, case-sensitive, and one-hop before provider and deployment
selection; alias chains, wildcards, fuzzy matching, and unknown-model fallback are
rejected. Alias keys must not collide with canonical IDs, targets must exist in
`FOUNDRY_MODELS_JSON`, and pricing must be keyed by canonical targets (alias price
overrides are rejected). Upstream JSON bodies and SSE bytes are preserved, including
the provider's reported `model`; an accepted alias therefore does not imply
equivalence to a specialized provider reviewer. Roll out or roll back by changing the
validated configuration through the normal drain/restart procedure; in-flight requests
settle against their captured canonical target. Bicep exposes optional nonsecret
`modelAliases` (default `{}`) through root/typed/container wiring into
`FOUNDRY_MODEL_ALIASES_JSON`.

## Shared Resource Credit (Implemented)

Set `credit_group` on each deployment backend belonging to the same resource credit account.
Omitted or null membership defaults to the backend ID. Any number of deployments and model pools
can share an account; the intended production topology is twelve deployment backends in six model
pools with two credit groups. Health remains backend-owned and provider quota remains `quota_group`-owned.

The existing `FOUNDRY_BACKEND_CYCLE_START_DAY_JSON`,
`FOUNDRY_BACKEND_CYCLE_ALLOWANCE_USD_JSON`,
`FOUNDRY_BACKEND_INITIAL_ESTIMATED_REMAINING_USD_JSON` and
`FOUNDRY_RECONCILIATION_OVERRIDES_USD_JSON` names remain compatible. Their keys must be canonical
credit-group IDs. Provide each account's cycle and estimates once; duplicated backend entries are
rejected. Group IDs reject blank values, surrounding whitespace, Table-forbidden/control characters
and UTF-16 encodings exceeding 1,024 bytes. A group cannot overlap a backend alias mapped elsewhere
or combine metered and non-metered backends. Missing values fail readiness and credit admission.

See [migration and operations](../operations/shared-resource-credit.md) before regrouping existing state.
Incomplete Table group initialization/config merge raises a typed failure and blocks routing;
failed Settings are not cached and can be retried unchanged after storage recovery.

## Google AI Studio Keys

Each Google AI Studio API key is configured as a separate backend with
`provider: "google_ai_studio"`, the compatibility endpoint, its Gemini model name, and its own
credential. Set `quota_group` to the Google Cloud project ID when multiple keys belong to one
project; those keys share RPM, input-TPM, RPD accounting, and cooldown state. When omitted, the
backend ID is used as the group. Only distinct projects add independent project quota.

`FOUNDRY_QUOTA_GROUP_RATE_LIMITS_JSON` maps configured quota-group IDs to active limits. Obtain
the values for each model and tier from the [AI Studio Rate Limits page](https://aistudio.google.com/rate-limit);
there is no universal limit triplet, and the values below are illustrative only:

```json
{"project-a": {"rpm": 15, "tpm": 1000000, "rpd": 1500}}
```

Groups with no configured limits are not tracked by the rate-limit store. Configured groups must
be declared by at least one backend. RPM and input TPM use a monotonic trailing-60-second window;
RPD resets at midnight Pacific Time with daylight-saving rules.

Set `credit_metered: false` on free-tier backends to opt out of dollar-credit assessment. A model
pool must be homogeneous: it cannot mix metered and non-metered backends because pricing and cost
are configured per logical model. An all-non-metered model always receives zero pricing,
regardless of any pricing entry. Metered pools still require explicit pricing and complete
per-credit-group configuration for readiness.

Each backend declares the operations it serves via `supported_operations`. Azure backends default
to `["responses", "embeddings"]`; Google backends default to `["responses"]` and must explicitly
declare `["embeddings"]` to serve embeddings (existing Google embeddings configurations must add
the declaration; there is no automatic model discovery). Empty, duplicated, or unknown operations
are rejected at config load.

Synthetic environment-loaded examples (placeholders only; never real keys, endpoints, or model IDs
beyond the documented compat root):

```bash
FOUNDRY_BACKENDS_JSON='{
  "gemini-text-a": {
    "provider": "google_ai_studio",
    "endpoint": "https://generativelanguage.googleapis.com",
    "credential": "${GEMINI_TEXT_A_KEY}",
    "deployment": "gemini-2.5-flash",
    "quota_group": "text-project",
    "credit_metered": false,
    "supported_operations": ["responses"]
  },
  "gemini-emb-a": {
    "provider": "google_ai_studio",
    "endpoint": "https://generativelanguage.googleapis.com",
    "credential": "${GEMINI_EMB_A_KEY}",
    "deployment": "gemini-embedding-001",
    "quota_group": "emb-project",
    "credit_metered": false,
    "supported_operations": ["embeddings"]
  }
}'
FOUNDRY_MODELS_JSON='{
  "gemini-text": {"backends": {"gemini-text-a": 1.0}},
  "gemini-embeddings": {"backends": {"gemini-emb-a": 1.0}}
}'
FOUNDRY_QUOTA_GROUP_RATE_LIMITS_JSON='{"text-project": {"rpm": 15, "tpm": 1000000, "rpd": 1500}}'
```

Paid (metered) Google pools keep `credit_metered: true` with explicit pricing and complete
per-credit-group cycle configuration; free-tier pools use `credit_metered: false` with zero
pricing. Non-metered opt-out affects dollar credit only; it never bypasses quota admission.
Paid balances and prices remain local operator estimates with no Google billing synchronization.

## Core Settings

The implementation validates client authentication, reconciliation interval, minimum credit reserve in dollars and percent, retry attempts and maximum delay, logging level, pricing, per-backend cycle start day, backend API version, and whether protected backends may be emergency fallbacks. It also validates optional per-backend local estimate and reconciliation inputs:

- `FOUNDRY_BACKEND_CYCLE_ALLOWANCE_USD_JSON`
- `FOUNDRY_BACKEND_INITIAL_ESTIMATED_REMAINING_USD_JSON`
- `FOUNDRY_RECONCILIATION_OVERRIDES_USD_JSON` (optional mock/adapter input for authoritative remaining values)

It also validates two request-intake and reservation-lifecycle bounds introduced in Phase 08:

- `FOUNDRY_MAX_REQUEST_BODY_BYTES` (default 2,097,152 bytes / 2 MiB): maximum accepted request body size, enforced before JSON parsing for `/openai/v1/responses` and `/openai/v1/embeddings`.
- `FOUNDRY_RESERVATION_MAX_AGE_SECONDS` (default 900 seconds): maximum reservation age before conservative settlement. Valid retained settlement intent wins; otherwise the full reserved estimate is charged, including legacy/pre-egress rows. Confirmed explicit releases charge zero.

The optional distributed state backend is `memory` by default. When `FOUNDRY_STATE_BACKEND=table`, configure `FOUNDRY_TABLE_ENDPOINT`, `FOUNDRY_TABLE_HEALTH_NAME`, and `FOUNDRY_TABLE_CREDIT_NAME`; the endpoint must be HTTPS and contain no credential or query string. `FOUNDRY_TABLE_REQUEST_TIMEOUT_SECONDS` bounds Table SDK connect/read timeouts. `FOUNDRY_RATE_LIMIT_REPLICA_SHARE` is set by Bicep from `maxReplicas` and divides configured provider quota limits per replica; readiness names any group/dimension whose effective share is zero. Storage fields are used when either credit/health or quota selects Table. Table-mode wiring and tests are implemented, but a two-replica Azure deployment and production cut-over remain unverified.

`GET /health/ready` reports whether every unique routable metered credit group has complete credit configuration and every configured model has pricing, surfacing incomplete configuration without failing config load outright. Non-metered backends are excluded only from dollar-credit completeness checks. Table probes require one balance row per routable metered group and still check health-table reachability for non-metered topology.

Pricing values and local credit balances are estimates; zero is valid for an uncharged dimension. Missing local credit estimates make a backend ineligible for credit-aware routing rather than defaulting to unlimited capacity. Reconciliation is Partially implemented through a periodic background loop that can apply externally supplied remaining-credit snapshots while preserving local fail-safe behavior.

## Authoritative Data

Keep these sources separate:

- Authoritative configuration.
- Authoritative Azure usage and cost data.
- Locally estimated usage and cost.
- Ephemeral health, cooldown, and inflight reservation state.

Local estimates must be labeled as estimates and must never be presented as exact balances.

## Opt-in Google tool, structured text and image profiles

`google_features` is a validated per-backend profile, defaulting to no enabled features.
Features: `function_tools`, `parallel_calls`, `json_object`, `json_schema`, `inline_images`.
Every multi-feature request must match an explicit `combinations` entry; individual support
never enables combinations. Tools require `continuation_policy: "unsigned"`. Signed
profiles are rejected at startup. Images require `image_input_tokens >= 258`,
`image_token_pricing: true`, and a Google-only logical pool. These declarations require actual
operator/model evidence before enablement; names do not infer support.

See [profile example and resource bounds](../operations/google-features.md).
`FOUNDRY_INTAKE_TIMEOUT_SECONDS` defaults to 30 (range 0.1–120), starting before Responses
and embeddings body intake. Remaining intake time bounds admission; Google delivery is bounded
by the tighter of remaining intake time and the original reservation deadline without reset.
Azure execution uses the reservation deadline only and is never truncated by body intake.
Body parsing rejects duplicate keys, nonfinite values and excessive depth/work. The default
request cap remains 2 MiB. Malformed `input` shapes fail with controlled validation errors.
Inspector child cleanup is bounded: a stalled reap transfers its single wait task to explicit
orphan tracking (never a second waiter) and releases capacity promptly. Tracking clears only
after successful, confirmed reaping (exit observed); failed or cancelled waits stay retained
against the admission limit with a warning diagnostic. New inspections are rejected when eight
killed-but-unreaped children are tracked per inspector pool. Already admitted inspections can
still transfer their children, temporarily exceeding that threshold; rejection continues until
reaping catches up, without suppressing request cancellation.

Google backends may explicitly select `api_surface: "native"` (Partially implemented local code;
review gates in progress). Default `openai_compat` preserves existing routing. Native requires
`supported_operations: ["responses"]`, service root and a profile affirming
`native_thinking_disabled: true`; no automatic surface switch or native embeddings route exists.
See [native contract/gates](../plans/google-ai-studio-tools-multimodal/native-pdf/index.md).

PDF profiles are **Implemented locally**, with independent review/resource/client gates passed; exact-model live validation remains pending. Default-off
`inline_pdfs` requires native transport and Google-native-only pools, `pdf_token_pricing: true`,
`pdf_input_tokens_per_page >= 258` and `pdf_native_text_tokens_per_page >= 65536` affirmed for the
exact model. Bounds: `max_pdfs`<=4, `max_pdf_bytes`<=65536, `max_total_pdf_bytes`<=131072,
`max_pdf_pages`<=4. Estimates reserve the full configured visual/text page ceiling and document
byte ceiling for every document. Worker readiness requires Linux, pinned pypdf and a successful
bounded isolated self-test. Do not enable pending profiles before their remaining gates pass.

Optional `FOUNDRY_GOOGLE_STATE_KEYS_JSON` is **Partially implemented** for the signed-continuation
increment. It contains secret canonical32byte caller-scope and1–3distinct Fernet keys, active key
ID, configuration generation and bounded TTL. Parsing rejects duplicate keys, invalid IDs, key
reuse and oversized configuration; keys are excluded from settings serialization. Successful
authentication derives a nonpublic caller binding under that scope key. This setting enables
no signed capability: profiles remain disabled until history/routing/native/client gates pass.
See [signed design/evidence](../plans/google-ai-studio-tools-multimodal/signed-continuation/evidence.md).

Finite WAV `inline_audio` is **Partially implemented**, default-off pending
[audio gates](../plans/google-ai-studio-tools-multimodal/audio-input/evidence.md). It requires
native Google-only pools, `audio_input_tokens_per_second` (32–10000), `audio_token_pricing: true`
and `audio_tpm_tokens: true`. Each file reserves configured seconds × rate + 64 input tokens;
pools use the maximum enabled backend bound. Free-tier zero-price still consumes input TPM.
Bounds: `max_audio_files`<=2, `max_audio_bytes`<=320044, `max_total_audio_bytes`<=640088,
`max_audio_seconds`<=10 and `max_total_audio_seconds`<=20. Exact model pricing and provider TPM
semantics must be verified before opt-in; operator declaration alone is not live evidence.

Finite AVI `inline_video` is **Partially implemented**, default-off; native Google-only pool,
`video_input_tokens_per_frame`>=258 (operator-affirmed ceiling), `video_token_pricing: true`,
`video_tpm_tokens: true`. Each clip reserves maxframes×rate+maxbytes+64; largest enabled backend
bound applies to the pool. Bounds: max_video_files2, max_video_bytes65536, max_total_video_bytes
131072, max_video_frames4, max_total_video_frames8, max_video_pixels4096. Fixed1fps determines
duration from frames; it does not establish model token counting. Exact combinations explicit.
See [video evidence](../plans/google-ai-studio-tools-multimodal/video-input/evidence.md).

Generated image `image_output` is **Partially implemented and startup gated**. Its finite
profile requires `generated_output_tokens_bound` (2048–32768),
`image_output_price_ceiling_usd`, `image_output_input_token_pricing`,
`image_output_quota_via_rpm`, `image_output_input_tpm_tokens`, `image_output_ipm` and
`native_thinking_disabled`. Only native Google pools with identical output profiles and
explicit project quota groups are eligible; RPM must not exceed IPM and input TPM is required.
Emergency fallback is incompatible. Separate `PricingConfig.image_output_per_image` must match
the declared ceiling; non-metered pools require zero image price. Every billable outcome retains
the full conservative input/output/image reserve. These estimates are not provider balances.
Settings rejects this feature until the remaining gates in
[generated image evidence](../plans/google-ai-studio-tools-multimodal/generated-image/evidence.md)
are cleared; adding profile fields does not enable it.

The gated generated-image implementation reserves both output capacity units for every request
in an `inline_images` output pool, including auto text-only requests. Such pools admit one
request at a time; output-only pools may admit two one-unit requests. Both share the same global
nonqueued capacity. This policy follows exact combined-cap resource measurements and does not
change project quotas, token bounds or full-reserve settlement.

Generated audio `audio_output` is **Partially implemented and startup gated**. The audio-only
native profile requires `generated_output_tokens_bound` (2048–32768), `audio_output_voices`,
`audio_output_thinking_policy` (`omit` or `disable_zero`) and explicit
`audio_output_thinking_affirmed`. Required price/quota fields are
`audio_output_price_ceiling_usd_per_second`, `audio_output_input_token_pricing`,
`audio_output_quota_via_rpm`, `audio_output_input_tpm_tokens` and `audio_output_rpm`.
Identical native profiles across a pool and explicit shared project groups are required;
project RPM cannot exceed the audio ceiling, input TPM must be configured, and emergency
fallback is incompatible. Separate `PricingConfig.audio_output_per_second` must match the
ceiling; non-metered audio pools require zero price. Every billable outcome retains the full
input/server TOTAL token allowance plus10seconds of audio cost; known usage updates input TPM
and public usage without generic output repricing. Settings rejects `audio_output` until
[remaining gates](../plans/google-ai-studio-tools-multimodal/generated-audio/evidence.md) pass.

## Shared quota configuration

**Implemented** locally with mocked API and real Azurite verification. Default
`FOUNDRY_RATE_LIMIT_BACKEND=memory` retains process-local replica shares. Opt-in `table`
uses identity-only `FOUNDRY_TABLE_ENDPOINT` and a separate `FOUNDRY_TABLE_QUOTA_NAME`
(default `routerquota`), independently of credit/health `FOUNDRY_STATE_BACKEND`.
Every backend quota group needs nonempty configured limits; shared Table limits are full
project/group limits and are not divided by `FOUNDRY_RATE_LIMIT_REPLICA_SHARE`.
Table quota reservation age must be positive and ≤3,600 seconds (default 900).

The store has a conservative 70-second minute window and blocks admissions in the
five-second interval on either side of Pacific midnight. Participating hosts must be
UTC-synchronized within five seconds; deployment clock and real provider admission remain
rollout gates. One atomic state row holds at most 256 retained attempts and 48 KiB of
serialized UTF-16 storage bytes per group; capacity fails closed. Each dispatched attempt,
including failover, consumes quota independently of monetary credit.
See the [shared quota plan](../plans/distributed-quota-accounting/index.md) for lifecycle,
policy fingerprints and drained rollout requirements. No production settings changed.

## Opt-in central metrics

**Implemented** locally. `FOUNDRY_TELEMETRY_ENABLED=true` enables cumulative OTLP metrics
alongside authenticated local Prometheus output. Supply an exact HTTPS
`FOUNDRY_TELEMETRY_ENDPOINT` ending `/v1/metrics`, optional secret
`FOUNDRY_TELEMETRY_AUTHORIZATION`, and `FOUNDRY_TELEMETRY_SERVICE_NAME`. Optional
`FOUNDRY_TELEMETRY_REPLICA_ID` and `FOUNDRY_TELEMETRY_REVISION_ID` identify topology;
each worker generates its own process-lifetime instance ID. No collector is provisioned.

Interval defaults to 15 seconds (5–60); timeout defaults to 3 seconds (1–10).
`FOUNDRY_TELEMETRY_SERIES_BUDGET` defaults to 2,048 (maximum 16,384); startup rejects
insufficient baseline capacity. Additional status combinations consume the same bounded
budget and are dropped at capacity, with safe local diagnostics. Request bodies, outputs,
credentials and request IDs never enter exported metrics. SDK-disable environment settings
fail enabled startup explicitly. Install the `telemetry` extra; the Docker image includes it.
