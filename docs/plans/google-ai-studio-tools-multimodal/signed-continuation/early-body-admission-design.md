# Admit signed JSON intake before buffering

**Planned**, 2026-10-06; independent review before runtime edits.

The current mixed/signed Responses path selects `offload_json` if any bound-history pool exists.
It buffers each bounded HTTP body before `bounded_signed_work` acquires the two shared slots.
Thus saturated requests rejected with 503 still allocate up to the body cap; repeated eight-caller
1.58 MiB traffic can increase process RSS despite only two worker jobs. Current unprofiled
preencoded scanner repeat fails 190,414,848 B / 52.72 ms; no resource gate closure claimed.

Propose feature-local `request_body` change only for existing `offload_json=True`: validate content
headers and declared body-size bound as before, acquire a `SignedWorkLease` before creating the
bytearray or reading `request.stream()`, then pass that lease to `bounded_signed_work` for JSON
parse. Close the lease in finally after read/parse, including invalid JSON, body limit, disconnect,
outer intake deadline and cancellation. If work remains active after caller timeout, close must
retain its slot until actual finish. Busy admission returns existing safe 503 before body read;
no prompts/media copied for saturated clients. A body read owns at most one of the existing two
slots and the original intake deadline, with no queue/wait. No additional slots, token reservations,
credit activity or provider egress. Non-offloaded unsigned/embeddings paths remain unchanged.

After successful parse, the route synchronously resolves/canonicalizes the model then acquires
its existing request-owned signed lease; verify no intervening await creates unbounded successful
parsed bodies. Unsigned models in mixed configuration already share offloaded parsing and must
release intake lease at parse completion, preserving their existing routing policy. Do not retain
an intake lease through unrelated unsigned downstream work. Reject a design that double-acquires
slots when submitting parser work or releases a running parser early.

Explicit tradeoff: slow body readers in mixed/signed configurations occupy these two shared
slots until the existing intake deadline; third arrivals fail immediately. Existing implementation
already shares parsing work across mixed pools, but reads previously occurred outside admission.
No cross-provider eligibility change, authorization bypass, new request deadline or global rate
limit. Validate this limited backpressure behavior and document it in operational/security docs.

Required tests: saturated intake calls receive no ASGI body chunks and allocate no bytearray;
two slow readers hold slots then time out, restoring capacity; invalid headers/oversize fail before
admission; chunk overflow, disconnect, parse failure/success, cancelled/latefailed active worker
close exactly once; unsigned nonoffloaded/embeddings unaffected. Actual SDK signed replay and
known billing, all local full/static/Docker/Linux/deepreview; sequential same-resource repeats
without profiling, limits unchanged. Startup/live/production remain gated.

Review clarification: saturated requests with unknown actual body length return 503 before read,
including bodies that would otherwise exceed the cap; declared oversize still returns 413 before
admission. Test those separately. Check incoming chunk length against remaining body budget before
extending the bytearray, so an oversized ASGI chunk is rejected without duplicating it. This
additional finite-read check applies to all request_body reads without changing accepted inputs.
Do not claim bounded lifetime for unsigned parsed bodies after intake lease release.
