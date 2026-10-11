# Amendment: bounded OpenRouter direct probes

Date: 2026-10-11. Status: **Planned**; independent review complete with changes
required before live execution. No live dispatches under this amendment yet.

[Independent commit review](review-direct-probe-607da09.md) initially identified three Major findings. Follow-up review of `7f0c207`
closes DP-2 (streaming response bounds). DP-1 remains open for lost initialized
state and pre-header dispatch accounting; DP-3 remains open for complete results
envelope/size validation. The amendment is not cleared for live probes.

## Background

Three OpenRouter models (free Gemma, paid GPT-4o-mini, paid Haiku) show the
identical provider-200/public-502 signature with valid observed usage. The
harness redacts raw envelopes by design, so the distinguishing shape evidence
was never captured. Router-side retries, model substitution, and live router
reruns remain refused under existing halts.

## Change

Authorize at most three direct, router-independent POSTs to
`https://openrouter.ai/api/v1/chat/completions` — one per model
(`google/gemma-4-26b-a4b-it:free`, `openai/gpt-4o-mini`,
`anthropic/claude-haiku-4.5`) — using the exact translated body the router
would send (model, one user message with short nonsensitive text,
`max_completion_tokens` 128). No router involvement, no retries, no streaming.

Each probe records structural evidence only: HTTP status, top-level and
message field names, finish reason, content classification
(missing/empty/whitespace/text/refusal/tool-calls/other) with byte length,
usage integers with a validity flag, and elapsed time. Content values, prompts
beyond the fixed nonsensitive text, error bodies, and credentials are never
persisted or printed. A bounded probe script (`openrouter_direct_probe.py`)
enforces the fixed three-model set, per-probe timeouts and byte bounds, exact
body matching, and a results-gated budget (each model probed at most once;
existing outcomes are never replayed). Credential comes from
`OPENROUTER_API_KEY` in the environment only.

## Rationale

The single unknown is the provider envelope shape. Capturing structure (not
content) distinguishes adapter strictness (e.g. empty content, extra fields,
unexpected finish reason) from provider contract gaps, and unblocks both the
OpenRouter translation question and the deferred Gemma/Muse diagnosis without
touching halted router runs.

## Exit criteria delta

- [x] Independent review of this amendment and the probe script recorded in the [review](review-direct-probe-607da09.md).
- [x] DP-2 streaming bounds fixed and independently verified in `7f0c207`.
- [ ] Remaining DP-1 and DP-3 gaps resolved and independently re-reviewed before any live probe.
- [ ] Each model probed at most once with structural evidence and no content,
      secret, or credential bytes recorded.
- [ ] Diagnosis recorded: adapter strictness vs provider contract, with any
      runtime fix proposed as a separately reviewed amendment.
- [ ] Billing, quota/admission, Table, and production remain gated.
