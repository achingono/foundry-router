# Incremental Google compatible stream lifecycle

**Planned**, 2026-10-09 UTC. Required Responses text workstream 2a still lacks real
incremental delivery/cancellation and nonzero thinking settlement evidence. The eight
successful prior compatible cases buffered upstream data in the verification guard; their
completion/settlement evidence remains valid but cannot clear these lifecycle gates.

## Execution and finite budget

Operator authorized all available free-tier budget using the existing five-string Key Vault
secret. Preserve the authoritative cumulative ledger and all prior failures; no reset or new
allowance. Project 1 has no slots and is excluded. Projects 2/3 each have two remaining slots,
projects 4/5 each three: at most ten dispatches total, 1,088 reserved tokens each, 1,024 output
and 64 input upper bounds, zero paid spend. Capture an immutable full baseline before running.
Ledger reserved totals do not decrease after observed usage. Any consumed slot without a
saved result halts its project; failed normal verification halts later cases for that project.
Overrun halts the entire stage. Refuse changed historical debits or unrelated new entries.
Single whole-stage lock shared with existing compatible stages; deterministic unique IDs.
Every dispatch/debit and partial usage must be durably saved before later awaits. The existing ledger records actual usage only once; add a verifier-owned monotonic progress updater under the same ledger lock for these new deterministic case IDs only. It may raise their observed actual token maximum and nonrefundable token debit, never lower it or modify historical cases. Preserve every partial maximum in bounded numeric progress/result evidence. Validate ledger prefix and recomputed caps on every update. Any dimension or total overrun halts the whole stage.

Exact model gemini-3.5-flash-lite, Google compatible Chat upstream translated through the
real local Responses route, provider-default thinking, no tools/state/media/embeddings.
Project 2/3: one ordinary incremental stream then one cancellation stream. Project 4/5:
one nonstream reasoning task, matching incremental reasoning stream, then cancellation.
Each later stream requires recorded preceding normal success. Freeze prompts: ordinary `Reply with the word ready.`, reasoning `Explain (17*23-19)/4 in three short steps.`, cancellation `List the integers from 1 to 200.`. Validate the exact wire request and ASCII prompt byte length plus 16 framing tokens <=64 before dispatch. This finite upper bound is an operator execution cap, not a provider tokenizer claim; observed input >64 is an overrun even when total<=1,088. Do not promise
that a harder task forces nonzero provider thinking; absent reasoning metadata stays unknown.

## Incremental observer and real client

Use a verifier-owned AsyncByteStream wrapper that forwards chunks immediately, without
waiting for full response or reading twice. A bounded incremental SSE observer captures usage
only: frame <=1 MiB, whole decoded response <= existing Google maximum, no raw text retained
beyond bounded parser state. Preserve SSE boundaries through the actual adapter and normal
route. Every observed usage frame contributes conservative maximum input/output/total;
validate integers, totals and thought subset independently. Record known partial usage before
further await. Never replace larger prior usage with a smaller final count. Do not expose
thought signatures, prompts, provider bodies or generated output in evidence.

Use a real loopback HTTP server/client for the local router, because httpx ASGITransport
buffers and cannot prove incremental network delivery. Own server socket/task and all clients
within one bounded lifetime. Disable access logging and use in-memory random caller keys.
Bind readiness before any dispatch; no public ingress, deployed app or production changes.
A complete normal stream must have actual public text delta before upstream EOF, completed event, matching public
usage/debit and zero reservations. Complete buffered delivery remains unverified for this incremental gate. Record monotonic first-upstream-chunk, first-public-text and
completion timings, and whether public text arrived before upstream EOF. This is observed
local delivery timing, not a production TTFT SLA.

For cancellation, disconnect immediately after the first meaningful public text delta. Track
that a real provider dispatch happened and upstream transport closed; confirm no second
attempt/failover and exact local conservative debit/reservation release after normal bounded
cleanup. If terminal usage was not observed, do not claim exact billed cost: preserve the
full reserved budget and label settlement conservative/usage unknown. Require natural disconnect teardown to close upstream and settle/release the reservation before any forced reaper. A reaper-assisted recovery may safely settle conservatively after failed natural cleanup, but must remain cleanup-failed/unverified and never clear cancellation. Partial numeric maxima are not terminal usage; terminal usage requires the observed final usage frame and normal protocol termination. Cancellation after already-observed upstream EOF does not clear live cancellation.
At most 30 seconds per case including teardown/status; request deadline 25 seconds leaves
cleanup headroom. Ambiguous cancellation or cleanup timeout halts the project and remains
unverified. No provider calls after cancellation, retries or polling inference.

## Workflow and evidence

Different-session concrete plan review before code. Test fragmented/multiline SSE, partial
and nonmonotonic usage, EOF/disconnect/failure cleanup, real loopback early delivery, durable
partial debit, overrun halt and replay/baseline gates using synthetic provider streams. Full
quality, >=80% coverage, contextual review; verifier-only changes need no Docker rebuild.
Commit plan, implementation, execution transitions. Successful cancellation clears only its
recorded model/project/local path. Nonzero thinking settlement requires actual provider
reasoning count >0, matching inclusive public output/debit; otherwise leave that gate open.
Capacity/project IDs, deployed admission/metrics, Table cut-over and all other roadmap gates
remain separate.

- [Inputs](inputs.md)
- [Activities](activities.md)
- [Outputs](outputs.md)
- [Exit criteria](exit-criteria.md)
- [Risks](risk-register.md)
- [Evidence](evidence.md)
