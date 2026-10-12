# Amendment: streaming direct probes

Date: 2026-10-11. Status: **Planned** live diagnosis; independent review
gate **cleared** for the three fixed streaming probes. No live dispatches
under this amendment yet.

The [follow-up review of 0addac3](review-streaming-probe-5e95aea.md#follow-up-review-of-0addac3)
closed all three initial Majors: compatibility with prior results (SP-1), SSE
evidence classification (SP-2), and chunk-dependent frame bounds (SP-3). The
existing reservation, no-replay, credential and response-bound gates remain
in force; historical outcomes and halted router runs stay preserved.

## Background

All three OpenRouter reruns pass non-streaming but fail streaming with public
and provider 200, observed usage present, and no terminal usage. The redacted
observer cannot distinguish content-bearing `reasoning` stream deltas (which
the strict decoder rejects) from provider streams ending without terminal
usage. Router-side streaming retries, model substitution, and live router
reruns remain refused under existing halts.

## Change

Authorize at most three direct streaming probes — one per model
(`google/gemma-4-26b-a4b-it:free`, `openai/gpt-4o-mini`,
`anthropic/claude-haiku-4.5`) — POSTing the router-equivalent streaming body
(`stream: true`, `stream_options: {include_usage: true}`) straight at
`https://openrouter.ai/api/v1/chat/completions`, observed incrementally with
the same byte/frame/timeout bounds. Each stream is classified structurally:
event count, per-event delta key sets, reasoning-delta presence and byte
length, text-delta byte length, finish reasons (enum or unexpected flag),
`[DONE]` observation, truncation, and usage integers with validity. Content
and delta values, error bodies, and credentials are never persisted or
printed. The existing results file, reservation lifecycle, atomic writes,
init identity, and credential handling extend unchanged to `*-stream` probe
IDs; each streams at most once and reruns refuse.

## Rationale

The single unknown is the stream shape. Presence of reasoning deltas directs a
decoder-tolerance amendment; absence with a clean `[DONE]` directs
terminator/usage handling instead. Either way the next step is evidence, not
guessing.

## Exit criteria delta

- [x] Independent review of this amendment and the streaming probe code recorded.
- [x] SP-1, SP-2 and SP-3 resolved and independently re-reviewed; dispatch gate cleared.
- [ ] Each model streamed at most once with structural evidence and no content,
      secret, or credential bytes recorded.
- [ ] Diagnosis recorded: reasoning deltas vs missing terminal usage, with any
      decoder change proposed as a separately reviewed amendment.
- [ ] Billing, quota/admission, Table, and production remain gated.
