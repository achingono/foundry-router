# Google AI Studio Adapter Evidence

## Status

**Implemented** with mocked verification (2026-10-05). This evidence log records planning work
plus code-verification results below; it does not assert Google service availability or
real-provider compatibility (live gate remains **Planned**).

## Evidence Log

| Item | Reference | Notes |
| --- | --- | --- |
| Planning baseline | `git status --short`; `git rev-parse --short HEAD` | Clean initial tree; commit `b6a188c`, inspected 2026-10-05 |
| Templates | [Templates](../../templates/index.md) | Copied index and all six companion templates into this directory before authoring |
| Existing provider support | [Backend client](../../../src/foundry_router/backends/__init__.py) | Google URL/header/model handling exists; Responses body/result schemas are not translated |
| Streaming baseline | [Forwarding](../../../src/foundry_router/forwarding/__init__.py) | Raw pass-through and terminal usage inspection exist; no Google-to-Responses event adapter |
| Embeddings quota gap | [Routes](../../../src/foundry_router/api/routes/openai.py) | Embeddings omits the quota store from routing/finalization |
| Existing tests inspected | [Backend tests](../../../tests/unit/test_backends.py), [integration](../../../tests/integration/test_full_flow.py), [stream tests](../../../tests/unit/test_forwarding_stream.py) | URL/auth/routing fixtures do not prove Google Responses schema compatibility |
| Concrete design | [Adapter contract](adapter-contract.md), [activities](activities.md) | Scope, mappings, boundaries, implementation dependencies and test cases documented |
| Independent plan/deep design review | Separate session `/root/review_google_adapter_plan`, 2026-10-05 | Applied architectural, business-logic, trust-boundary and resource-economic themes from the deep-review prompt; two Major findings and two Suggestions addressed; follow-up review confirmed no blocking plan findings remain |
| Documentation validation | Relative-link checker using `.venv/bin/python`; whitespace/diff review | 104 relative targets across nine touched Markdown files resolve; no unfilled template markers or trailing whitespace; `git diff --check` passes; content reviewed for secrets and unsupported status claims |
| SonarQube script | `scripts/quality/sonarqube-scan.sh` absent in inspected tree | No scanner executed; rechecked at implementation time, still absent |
| Runtime verification | Not run for this planning-only change | Full suite, coverage, lint/type/build and live Google checks remain implementation gates |
| Cross-plan review | [Consolidated review](../cross-plan-review-2026-10-05.md), 2026-10-05 | Reviewed alongside tools/multimodal and model-aliases plans; 3 minor findings recorded; plan approved for implementation |
| W1 vendor confirmation | Public docs verified 2026-10-05 (OpenAI compat, rate limits, Responses reference) | Base path `/v1beta/openai/`, Bearer auth, `max_completion_tokens`, `stream_options.include_usage`, `[DONE]` + usage-only finals, stop/length/content_filter mapping; recorded in ADR-008 |
| Implementation | `src/foundry_router/api/adapters/`, `config/`, `backends/`, `routing/`, `forwarding/`, `credit.py`, `api/routes/` | Adapters, operation eligibility, non-streaming/embeddings/streaming translation, bounded reads, narrowed retries, auth cooldown, billable settlement implemented |
| Focused tests | `pytest tests/unit/test_backends.py tests/unit/test_config.py tests/unit/test_forwarding_stream.py tests/unit/test_ratelimit.py tests/integration/test_full_flow.py tests/unit/test_google_adapter.py tests/integration/test_google_adapter_integration.py tests/unit/test_google_lifecycle.py -q` | 168 passed |
| Full suite | `pytest tests/unit/ tests/integration/ -m "not docker and not azurite" --cov --cov-fail-under=80` | 504 passed, total coverage 84.80% |
| Lint/format/types | `ruff check src/`, `ruff format`, `mypy src/` | All checks passed; `mypy` clean on 29 source files |
| Docker build | `docker build` + image health smoke (rebuilt as `:nine-fixes-final` after lifecycle fixes) | All builds passed; `/health/live` returned `{"status":"alive"}` in test containers |
| Live Google validation | Not run (no operator credentials) | Gate remains **Planned**; code tests alone never close it |

## Review Dispositions

| Finding | Severity | Disposition |
| --- | --- | --- |
| Ambiguous dispatched attempts could consume paid credit and then retry using one reserve | Major | Google now retries only confirmed pre-dispatch/non-generation failures; ambiguous attempts retain quota, settle usage/estimate and terminate. W5 and exit criteria require lifecycle tests. |
| Invalid highest-ranked Google credential could starve healthy keys on later requests | Major | Google 401/403 enters backend-local bounded `ERROR_COOLDOWN`; no same-request cycling; later selection and expiry tests required. |
| A body-size check after `AsyncClient.request()` would occur after buffering | Suggestion | Require incremental decoded-byte reads and chunked/compressed-limit tests. |
| A new stream timer could exceed an already-aged reservation | Suggestion | Preserve an absolute initial-reservation deadline across retry waits, prefetch, failover, slow consumers and cleanup. |

The independent session inspected the revised contract, activities, exit criteria and risk
register and confirmed all four findings resolved. This is a design review of a planning-only
change, not implementation, vendor-contract or real-inference verification. W1 remains required.

## Cross-Plan Review Findings

Independent cross-plan review session, 2026-10-05. Reviewed alongside
`google-ai-studio-tools-multimodal` and `model-aliases` plans.

| Finding | Severity | Disposition |
| --- | --- | --- |
| Baseline commit references (`b6a188c`) pre-date two subsequent doc-only commits; HEAD is now `1c043fd` | Minor | Update references in `index.md`, `inputs.md` and `evidence.md` during W1 when confirming baseline; no runtime code changed between commits |
| Google `/v1beta/openai/chat/completions` may expect `max_tokens` or `max_completion_tokens`; plan flags this for W1 but does not prescribe a default | Minor | Already captured as a W1 verification task; confirm during vendor contract confirmation and record the result in the ADR |
| Adding `supported_operations` to `BackendConfig` must preserve backward compatibility for existing configurations | Minor | Default to `["responses", "embeddings"]` for Azure backends and `["responses"]` for Google backends when omitted, matching the W2 migration note |

Verdict: **Approved for implementation** with no blocking findings. All three items are
addressable during early implementation activities (W1/W2) without plan revision.

## Implementation Evidence to Add Later

Record W1 vendor confirmation dates, test commands/results, measured coverage, CI/Azurite/Docker
results, independent code review findings and fixes, and exact optional live-verification scope.
Never substitute a planned command, historical Phase 09 result or mocked result for current
real-provider evidence. Do not retain keys, prompts or model outputs.

## Implementation Deep-Review Dispositions (2026-10-05)

Independent deep-review of the implementation (architectural/business-logic/trust-boundary/
resource-economic themes) returned two Critical, four Major, and two Suggestion findings.
All are dispositioned below; code changes were re-verified (focused + full suites, coverage,
ruff, mypy) after fixes.

| Finding | Severity | Disposition |
| --- | --- | --- |
| Fail-open adapter translation/gating fallbacks could egress unvalidated requests | Critical | Fixed: `_build_upstream_body` propagates adapter errors (callers return sanitized 502 with no egress; identity only for legacy doubles without backend configs); routing `_backend_feature_rejection` fails closed with 422 on adapter exceptions |
| Google 5xx never fails over (availability concern) | Critical | Rejected by design: the plan deliberately narrows Google retries (5xx is not proof of non-generation; a second dispatch could double-bill one reservation). Documented in the settlement table in `forwarding` and the adapter contract; Azure policy unchanged |
| Empty deltas validated downstream and missing finish defaulted to `stop` (empty success) | Major | Fixed: decoder validates only on text or finish reason; `_terminal_events` raises without a finish reason, so truncation never becomes a successful completion |
| Usage absorbed before validation with zero-default output (undercharge) | Major | Fixed: envelope validated before usage absorption; precise settlement requires both token dimensions, otherwise conservative fallback; non-streaming omits public usage on incomplete usage instead of fabricating zero |
| Double model substitution and single-strip endpoint normalization | Major | Partially fixed: endpoint config now rejects operation paths (`/chat/completions`, `/embeddings`); single compat-root strip retained for the valid root form. Model substitution stays idempotent across adapter/client (documented; harmless duplicate application of the same deployment) |
| Inconsistent settlement across error branches | Major | Clarified by design: confirmed non-generation rejections (4xx/5xx statuses) refund via the standard finalizer (quota estimates retained); possible-dispatch failures force-charge usage/estimate. Settlement table documented in `_forward_google_non_streaming`; quota finalization verified on all routing paths |
| First-rejection-only messaging; repeated capability checks | Suggestion | Accepted as designed (plan requires the relevant singular error); aggregation deferred to a follow-up |
| `_past_deadline` stub and confusing overhead naming | Suggestion | Fixed: stub and dead branch removed (streaming enforces the real absolute deadline); framing variable renamed with translation link |

## Runtime Lifecycle Review Dispositions (2026-10-05)

A second review round reproduced nine runtime contract and lifecycle gaps with synthetic
reproductions (no repository files changed). All nine are fixed below and covered by
`tests/unit/test_google_lifecycle.py` plus additions to `tests/unit/test_google_adapter.py`;
the full suite (504 passed), coverage (84.80%), ruff, mypy, and `git diff --check` pass after
the fixes.

| Finding | Severity | Disposition |
| --- | --- | --- |
| Cancellation during the non-streaming body read leaked the connection and refunded billable work | Major | Fixed: `CancelledError` during connect/read/prefetch is converted to a terminal force-charge outcome via `_shielded_google_cancel_cleanup` (bounded shielded close + cooldown), so routing settles the estimate and retains quota instead of refunding |
| Reservation deadline anchored in forwarding and polled only on chunk arrival | Major | Fixed: routing computes the absolute deadline once at initial reservation creation and enforces it around both backend attempts (retained across failover) with synthesized billable settlement on expiry; forwarding bounds reads/prefetch/delivery with per-operation timeouts against the same lifetime |
| Google 5xx refunded ambiguous consumption | Major | Fixed: 5xx terminal results now carry `force_charge` with the reservation estimate in both non-streaming and streaming pre-commit paths; only provider validation rejections (non-429 4xx) refund |
| Partial usage fabricated zero output on translation failure | Major | Fixed: `known_output` requires a valid `completion_tokens`; prompt-only usage falls back to the full conservative estimate in settlement |
| Embedding failures settled with a Responses cost estimate | Major | Fixed: `_fallback_estimate_cost` takes the actual operation; embeddings failures settle the input-only embeddings estimate with zero output allowance |
| 429 retried inside forwarding without fresh quota admission | Major | Fixed: Google attempts are single-shot per backend (no internal sleep/retry); 429 returns failover-eligible and routing admits the second attempt fresh while retaining the first attempt's quota via finalization. Dead jitter branch removed |
| Numeric message content raised `TypeError` outside the protocol-error path | Major | Fixed: response content shape is validated before extraction (non-string/non-list content, non-text parts, and non-string text fields raise `ValueError`); `_extract_text` raises `ValueError`, never `TypeError` |
| Hand-built `response.failed` events lacked sequence, identity, and status | Major | Fixed: `GoogleStreamDecoder.build_failure()` emits terminal `response.failed` with the decoder's response identity, monotonically increasing sequence numbers, `failed` status, and known usage; exactly-once via the terminal latch. Forwarding uses it for all post-commit failures |
| Embedding results were not checked against the request | Major | Fixed: `translate_success` accepts `expected_input_count`/`expected_dimensions` (derived from the public embeddings request); count and dimension mismatches are sanitized protocol failures with conservative settlement |

## Repeated-Cancellation and Delivery Re-review (2026-10-05)

The three further Major findings are addressed with executable regression cases in
`tests/unit/test_google_lifecycle.py`:

- Repeated cancellation during blocked connection close uses `protected_cleanup`:
  close and cooldown have independent finite deadlines and remain joined through repeated
  cancellation. Billable credit/quota settlement is independently protected in routing;
  a failed or timed-out close cannot change settlement into a refund.
- Routing supplies one absolute deadline explicitly to the route callback and forwarding,
  retaining it across failover. The deadline starts before admission to include storage
  latency. `DeadlineStreamingResponse` wraps actual ASGI delivery, including response-start
  and body sends, in `asyncio.timeout_at`. Its finalizer closes the suspended generator;
  a fallback settles an upstream whose generator never started because response-start blocked.
- Confirmed pre-dispatch expiry carries `confirmed_pre_dispatch`, releases the undispatched
  quota reservation, and refunds its credit. In-flight timeout remains conservatively billable.

Tests reproduce blocked close plus a second cancellation, blocked ASGI start/body sends, and
expiry during second-backend admission. Verification: **508 passed**, **85.91%** coverage;
Ruff check/format, mypy, and `git diff --check` pass. The Docker image rebuilt successfully
as `foundry-router:lifecycle-review`. Azurite and image-health results from prior rounds
are historical; these local results do not establish real Google inference.

## Post-Read Cancellation Re-review (2026-10-05)

The additional Major finding at normal connection closure and health activation is fixed:
the entire Google non-streaming attempt now runs inside a cancellation boundary with
retained `GoogleAttemptSettlement` facts. Valid usage is captured immediately after a
successful bounded body read, before normal close or any subsequent health-store await.
Cancellation at either point runs bounded cancellation-resistant cleanup and returns a
terminal billable result carrying known usage (or the conservative estimate when unknown).
Routing's independently protected settlement retains quota and cannot fall into its refund
fallback. The same boundary covers buffered transport and other post-dispatch awaits.

Two regressions cancel while normal close or `set_backend_active` is blocked after a valid
200 response: the upstream closes, actual generation cost is debited, one RPM entry and
four reported input tokens remain recorded, no failover occurs, and no credit reservation
remains. Full local verification: **510 passed**, **85.95%** coverage; Ruff, mypy, and
whitespace checks pass. Docker rebuilt successfully as
`foundry-router:post-read-cancellation`. Real Google inference remains **Planned**.

## Streaming Pre-Handoff Re-review (2026-10-05)

The Major finding for cancellation during streaming health activation and `httpx.ReadError`
during a 5xx error-body read is fixed. Google streaming now has an attempt-wide boundary
covering cancellation, HTTP transport/read errors, and timeouts until a downstream response
is returned. Shared `GoogleAttemptSettlement` facts retain the dispatched connection and
decoder. The boundary captures valid decoded usage, performs bounded cancellation-resistant
close/cooldown, and returns a non-retryable billable outcome. Only after successful return
does `DeadlineStreamingResponse` own subsequent delivery/settlement cleanup.

Regressions reproduce both exits through routing. Health-update cancellation charges the
decoded actual usage; a failed 5xx body read charges the estimate. Both close the upstream,
retain RPM/input-token consumption, prohibit failover, and leave no active reservation.
Full local verification: **512 passed**, **86.12%** coverage. Real Google inference remains
**Planned**.

## Stream Envelopes and Message Contract Review (2026-10-05)

Five Major findings and two Suggestions from the supplied deep review are addressed:

- Provider `error` SSE envelopes are recognized before choice/usage handling, without
  retaining or echoing provider messages. They terminate immediately through the decoder's
  `response.failed` path, with backend cooldown and bounded settlement/transport cleanup.
- Embeddings translation failures reconcile valid reported `prompt_tokens` with zero output
  tokens, matching attempt settlement; incomplete Responses usage still retains its estimate.
- Empty/whitespace-only history strings or parts return 422 `invalid_request` before admission
  and egress. System/developer text parts are concatenated in order into system string content.
- Non-null non-object stream usage is a protocol failure for both usage-only and choice-bearing
  chunks; absent/null usage remains allowed by the compatibility contract.
- Metadata is passed separately to JSON translation and stream decoders, echoed in public
  lifecycle/terminal responses, and omitted upstream. Validation enforces 16 entries, string
  keys up to 64 characters, and string values up to 512 characters.
- Stream settlement rejects negative/non-finite calculated cost and retains the estimate.

Regression evidence: `tests/unit/test_google_review_contracts.py` and the embeddings lifecycle
test reproduce these contracts, redaction, immediate failure, and actual-usage settlement.
Full local suite: **527 passed**, **86.83%** coverage; lint/type/format verification passes.
Provider support and real inference remain scoped to the previously documented live gate.
