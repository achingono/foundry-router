# Live verification activities

1. Complete independent plan review and resolve findings. The [review](review.md)
   clears the revised planning contract; harness implementation remains Planned.
2. Prepare the isolated harness and offline evidence described below. Review its
   implementation before any live request. Runtime fixes require a separately
   reviewed amendment; this plan permits verification tooling only.
3. Prepare a dedicated configuration: memory state, single replica, one Zen
   backend, one OpenRouter chat backend and one OpenRouter embeddings backend,
   each in its own logical pool with explicit test prices and complete credit
   inputs. Declare embeddings support explicitly. Load credentials out of band
   from environment variables or token-authenticated vault reads. Check local
   configuration, client/admin authentication, `/health/live`, `/health/ready`
   and zero initial reservations without displaying secrets. Readiness does not
   validate upstream credentials.
4. Initialize and bind the fixed manifest/ledger once, then hold the exclusive
   run lock across validation, requests and durable outcome writes. Execute the
   manifest's listed cases sequentially; every predecessor must have a validated,
   persisted pass before its successor may dispatch. The manifest lists a
   non-empty leading prefix of the fixed order below; unlisted cases are never
   dispatched. The current run lists the first four (Stages 1–2); the embeddings
   case awaits its own reviewed run.

   | Stage | Case ID | Request |
   | --- | --- | --- |
   | 1 | `zen-nonstream` | One Zen Responses request |
   | 1 | `zen-stream` | One Zen streaming Responses request |
   | 2 | `openrouter-nonstream` | One OpenRouter Responses request |
   | 2 | `openrouter-stream` | One OpenRouter streaming Responses request |
   | 3 | `openrouter-embeddings` | One OpenRouter embeddings request |

5. For each case, capture its initial canonical credit-group snapshot, durably
   reserve its case ID/budget slot before provider egress, observe the request,
   validate the public result and poll admin diagnostics for cleanup. Persist
   the sanitized result before any subsequent dispatch. Every failure blocks
   remaining cases, including upstream 401/403, 429, protocol failures, invalid
   usage, settlement mismatches and cleanup timeouts. No retry, direct upstream
   probe, alternative model or replacement credential dispatch is authorized.
6. Document exact successful/failing scope and obtain contextual evidence review.
   Keep other models, billing, quota/admission, Table inference and production
   separately gated. Any later rerun needs a reviewed amendment preserving all
   earlier dispatch records and explicitly defining a new budget.

## Durable execution contract

- The ledger is separate from router memory and uses durable atomic writes. A
  case reservation is a conservative possible-dispatch debit even if a crash
  occurs before the network send. Each fixed ID may reach transport at most once;
  disable client/transport retries and reject unexpected URLs, operations, models
  or request bodies at the observer boundary.
- On restart, validate manifest identity, ledger and result schema before any
  egress. Skip persisted passes. A reserved case without a valid outcome, any
  persisted failure, missing initialized state, corruption or write failure
  blocks the run pending review. Never reconstruct success from a missing result
  or refund an uncertain slot. Exclusive locking prevents concurrent invocations
  from admitting the same case. Terminal completion cannot reset the run.
- Bound each inference case to 120 seconds overall and 1 MiB of observed response
  bytes; bound an SSE frame to 256 KiB. Responses use fixed nonsensitive text
  inputs of at most 1 KiB and `max_output_tokens <= 128`. Embeddings uses two
  distinct short inputs totaling at most 1 KiB, float encoding, in one call.
  Poll cleanup at most ten times, one second apart, with a five-second timeout
  per diagnostic call. A bound breach fails and halts, with ambiguous dispatch
  conservatively retained in the ledger.

## Observation and acceptance contract

- Use a test-only transport observer around the real upstream transport; record
  provider HTTP status before router error translation. Parse provider usage
  independently of router adapter/settlement helpers. Missing or invalid usage
  fails acceptance; do not substitute zero or the reservation estimate. Capture
  public HTTP status separately, including public 502 versus provider 401/403.
  Transport failures may have no observed provider status.
- For Responses require HTTP 200, completed terminal state, nonempty text,
  nonnegative integer input/output counts and output within the configured cap.
  Compare Zen input/output usage directly; compare OpenRouter prompt/completion
  usage with public input/output usage. Reject failed/incomplete/truncated streams.
  Require Zen `response.completed` and OpenRouter upstream `[DONE]`, plus valid
  terminal usage and the public completed lifecycle. Preserve SSE delimiters
  across arbitrary transport chunks. Compare Zen upstream/public frames in memory;
  OpenRouter translates frames, so check complete parsed upstream and public
  lifecycles rather than byte equality.
- Observe incrementally without accumulating an entire upstream stream before
  router consumption. Keep prompts, outputs, vectors, raw frames, credentials
  and error bodies out of files, logs and console output. Emit only allow-listed
  statuses, counts, numeric deltas and acceptance flags; sanitize exceptions.
- Embeddings must return two indexed vectors in the expected order, equal
  positive dimensions, finite numeric elements and mapped input usage matching
  the upstream. Compare upstream/public indices and vectors transiently; persist
  only counts, dimensions and comparison flags. Require zero retained
  reservations and inflight credit for embeddings as for Responses.
- Calculate each expected local debit from independently observed upstream usage
  and approved input/output test prices. Compare against the before/after
  canonical `/admin/status` `credit_groups` balance delta with absolute tolerance
  `1e-9` USD; do not use rounded per-backend balances. Keep the isolated account
  free from concurrent traffic/reconciliation and refuse cross-cycle or restarted
  state comparisons. Choose test prices making nonzero debits observable above
  the tolerance. Record prices, counts, before/after balances, expected/observed
  debit and zero-reservation checks. These are estimates, unrelated to billing.

## Offline gate before live use

Test crash after intent/before outcome, restart after success/failure, missing or
corrupt state, manifest mismatch, concurrent invocations and persistence failure.
Assert no second dispatch for a reserved case and no successor after failure.
Inject public/provider status differences, deliberately mismapped usage, missing
usage, fragmented/truncated SSE, embeddings ordering errors, time/byte bound
breaches and secret-bearing errors; verify rejection and redacted evidence.
Run focused tests followed by the repository's applicable full verification,
coverage, lint/format/type, build, conditional scan and contextual review gates.
Record results before considering live execution ready.
