# Live verification activities

1. Obtain independent plan review and resolve findings before any live dispatch.
2. Prepare a dedicated test configuration (memory state, single replica, no
   production values): one Zen backend, one OpenRouter chat backend, one
   OpenRouter embeddings backend, each in its own logical pool with explicit
   test pricing and complete credit inputs. Load credentials from the
   environment only; verify `/health/live` and `/health/ready` without
   displaying values.
3. Stage 1 (Zen): send one non-streaming then one streaming Responses request
   with short nonsensitive text and `max_output_tokens` at most 128,
   sequentially. Verify HTTP status, completed output presence, and
   input/output usage counts without displaying content. Confirm terminal
   streaming usage and preserved SSE frames. Poll admin diagnostics with
   bounded retries until no active reservations or inflight credit remain;
   compare the local estimated debit against returned usage at test prices.
4. Record Stage 1 numeric outcomes before any further dispatch. On ambiguous
   dispatched failure, halt the stage persistently and record the halt; do not
   retry after meaningful stream output.
5. Stage 2 (OpenRouter chat): same non-streaming/streaming pair and checks
   against the operator-selected exact namespaced model. Verify translated
   output text, mapped usage, and settlement. Record numerics; halt on
   ambiguity as in step 4.
6. Stage 3 (OpenRouter embeddings): one short-input embeddings call against
   the operator-selected exact embedding model. Verify returned
   count/order/dimensions and input-token reconciliation. Record numerics.
7. Document exact successful/failing scope, independent contextual review, and
   relative links in [evidence](evidence.md). No code changes unless a real
   defect is established; any fix requires a separately reviewed amendment and
   repeated mocked suites before further live dispatches.

## Review focus

- Stage/halt discipline and the six-dispatch budget.
- Credential handling (out-of-band only, nothing recorded).
- Numeric-only evidence with no prompts, outputs, error bodies, or key values.
- Explicit non-claims for other models, billing, quota, Table, and production.
