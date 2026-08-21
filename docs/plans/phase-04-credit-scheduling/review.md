# Deep-Dive Architecture & Code Review Report

**Scope:** Phase 4 (Credit-Aware Scheduling) & All Prior Phases (Phases 1–3 Foundation, Auth, Forwarding, Health & Routing)  
**Methodology:** Contextual, business logic, architectural, security trust boundary, performance economics, and maintainability analysis beyond SonarQube static analysis.

---

### Summary of Findings

| Severity | Category | Module / Area | Summary |
| :--- | :--- | :--- | :--- |
| **Critical** | Resource Economics / Concurrency | [`src/foundry_router/main.py`](../../src/foundry_router/main.py#L362-L460) | In-flight credit reservation leak on `asyncio.CancelledError` and uncaught secondary failover exceptions |
| **Critical** | Business Logic / Intent | [`src/foundry_router/main.py`](../../src/foundry_router/main.py#L372-L440) | Non-2xx upstream responses (4xx/5xx) incorrectly charge full default 4,096-token reservations |
| **Major** | Observability / Traceability | [`src/foundry_router/main.py`](../../src/foundry_router/main.py#L265-L305) | Explainable routing structured decision logging missing (ADR-006 requirement violation) |
| **Major** | Quality & Verification | [`src/foundry_router/credit.py`](../../src/foundry_router/credit.py) | `credit.py` test coverage (70.71%) below 80% threshold and missing dedicated unit test suite |
| **Major** | Performance Economics | [`src/foundry_router/main.py`](../../src/foundry_router/main.py#L1038-L1081) | Repeated JSON deserialization and settings validation in the hot request path |
| **Suggestion** | Resource Economics | [`src/foundry_router/main.py`](../../src/foundry_router/main.py#L832-L860) | Streaming usage extraction from final chunk not parsed, over-deducting estimated credit |
| **Suggestion** | Maintainability | [`src/foundry_router/main.py`](../../src/foundry_router/main.py#L1039) | Redundant pre-validation call to `_select_backend` |

---

### Detailed Findings

### Recommendation Application Status (2026-08-21)

| Finding | Status | Notes |
| :--- | :--- | :--- |
| 1. In-flight reservation leaks on cancellation and failover exceptions | **Implemented** | `_execute_with_single_failover` now guarantees reservation cleanup with a top-level `try...finally`, including `asyncio.CancelledError` and secondary-backend exceptions. |
| 2. Non-2xx responses charged full reservation | **Implemented** | `_finalize_non_streaming_credit` now charges only for successful 2xx responses and releases reservations without charge for non-2xx responses. |
| 3. Missing explainable routing decision logging | **Implemented** | `_select_candidate_backend` now emits structured `routing_decision` events with candidate health/credit fields, score, reason, selected backend, and request estimate. |
| 4. `credit.py` coverage below 80% and missing dedicated suite | **Implemented** | Added dedicated `tests/unit/test_credit.py` coverage for cycle windows, token/usage estimation, reservation/finalization, rollover, and scoring. Module coverage now 91.07%. |
| 5. Repeated settings deserialization in hot path | **Implemented** | `load_settings()` now uses a single-entry `lru_cache`, and tests clear cache per case where environment mutations are expected. |
| 6. Streaming terminal usage not used for final charge | **Implemented** | `_stream_response` now parses SSE `data:` events for terminal `usage` payloads and finalizes with exact charged cost when usage is present. |
| 7. Redundant pre-validation model check | **Implemented** | `create_response` and `create_embeddings` now validate with direct `model in settings.models` checks instead of pre-selecting a backend. |

#### 1. In-Flight Reservation Leaks on Request Cancellation & Secondary Failover Failures

* **Severity:** **Critical**
* **File/Module:** [`src/foundry_router/main.py:362-460`](../../src/foundry_router/main.py#L362-L460) interacting with [`src/foundry_router/credit.py`](../../src/foundry_router/credit.py#L325-L385)
* **The Issue:**  
  `_execute_with_single_failover` wraps only the first backend execution in a `try...except Exception:` block:
  1. In Python 3.8+, `asyncio.CancelledError` derives from `BaseException`, not `Exception`. When a client drops the connection or a timeout cancels the coroutine during `execute_backend(first_backend_id)`, `except Exception:` does not catch it.
  2. The second backend execution on line 442 (`second_result = await execute_backend(second_backend_id)`) has **no** exception handler or `finally` block at all.
* **Why Static Analysis Missed It:**  
  Static analyzers verify syntax and exception types within individual blocks, but cannot detect unhandled `BaseException` cancellations in asynchronous task lifecycles or trace distributed reservation cleanup invariants.
* **Impact:**  
  Every cancelled request or unhandled secondary failover exception leaves an active reservation in `_reservations` and permanently locks `reserved_inflight_usd` on the backend snapshot. Over time in production under real-world client disconnects, `available_credit` shrinks to `$0.00`, causing healthy backends to be classified as `PROTECTED` or `INSUFFICIENT_CAPACITY`, triggering cascading `503 Service Unavailable` outages.
* **Recommended Fix:**  
  Enclose the entire failover and execution lifecycle in a `try...finally` block to guarantee `_credit_store.finalize_request(...)` is invoked exactly once on every exit path:

  ```python
  async def _execute_with_single_failover(...):
      first_selection = await _select_candidate_backend(...)
      if first_selection.backend_id is None:
          # handle exhaustion/rejection before reservation
          return ...
      
      reservation_finalized = False
      try:
          first_result = await execute_backend(first_selection.backend_id)
          if not first_result.retryable_failure:
              if not isinstance(first_result.response, StreamingResponse):
                  await _finalize_non_streaming_credit(
                      request_id=request_id,
                      model=model,
                      settings=settings,
                      response=first_result.response,
                  )
                  reservation_finalized = True
              return first_result.response

          # Failover execution...
          second_selection = await _select_candidate_backend(..., excluded={first_selection.backend_id})
          if second_selection.backend_id is None:
              ...
              return ...
          
          second_result = await execute_backend(second_selection.backend_id)
          if not isinstance(second_result.response, StreamingResponse):
              await _finalize_non_streaming_credit(
                  request_id=request_id,
                  model=model,
                  settings=settings,
                  response=second_result.response,
              )
              reservation_finalized = True
          return second_result.response
      finally:
          if not reservation_finalized:
              await _credit_store.finalize_request(
                  request_id,
                  charge_reserved=False,
                  charged_cost_usd=None,
              )
  ```

---

#### 2. Non-2xx Upstream Responses (4xx/5xx) Incorrectly Charge Full 4,096-Token Default Reservation

* **Severity:** **Critical**
* **File/Module:** [`src/foundry_router/main.py:374-440`](../../src/foundry_router/main.py#L374-L440) & [`src/foundry_router/credit.py:389-409`](../../src/foundry_router/credit.py#L389-L409)
* **The Issue:**  
  When an upstream backend rejects a request with an error (e.g. `400 Bad Request`, `422 Unprocessable Entity`), or when all failover attempts fail and return a `500`/`502`/`503`, the router calls `_finalize_non_streaming_credit(..., charge_reserved=True)`.  
  Because an error response contains no token `usage` metadata, `estimate_response_usage_cost` returns `None`. `_release_locked` then falls back to `elif charge_reserved: charge = reservation.estimated_cost_usd`, deducting the maximum conservative estimate (typically 4,096 output tokens) from `snapshot.estimated_remaining_usd`.
* **Why Static Analysis Missed It:**  
  The logic is type-safe and syntactically valid. Static analysis tools cannot determine that upstream Azure OpenAI does not bill for rejected 4xx or failed 5xx requests.
* **Impact:**  
  Malicious or malformed client requests returning 400s or transient upstream outages will rapidly deplete the backend's local estimated credit balance, artificially starving legitimate requests.
* **Recommended Fix:**  
  Only charge credit against the backend when the upstream response has a successful `2xx` status code. If the response is non-2xx, release the reservation without debiting the backend's remaining balance:

  ```python
  async def _finalize_non_streaming_credit(
      *,
      request_id: str,
      model: str,
      settings: Any,
      response: Response,
  ) -> None:
      is_success = HTTP_OK <= response.status_code < HTTP_SUCCESS_LIMIT
      charged_cost = (
          estimate_response_usage_cost(response, model, settings.pricing)
          if is_success
          else 0.0
      )
      await _credit_store.finalize_request(
          request_id,
          charge_reserved=is_success,
          charged_cost_usd=charged_cost if is_success else 0.0,
      )
  ```

---

#### 3. Missing Explainable Routing Decision Logging

* **Severity:** **Major**
* **File/Module:** [`src/foundry_router/main.py:265-305`](../../src/foundry_router/main.py#L265-L305)
* **The Issue:**  
  ADR-006, `docs/features/routing.md`, and Phase 04 Activity 9 specify: *"Every decision should expose model, selected backend, candidate states, scores, credit estimates, days remaining, and reason through structured debug data or authenticated status."*  
  `_select_candidate_backend` computes the ADR-006 composite scores across candidates but never emits structured logs detailing the evaluated scores, candidate states, or decision rationale.
* **Why Static Analysis Missed It:**  
  Static analyzers check if logging imports are valid and syntax is clean, but cannot check whether runtime code satisfies specific architectural observability policies.
* **Impact:**  
  Operators have zero visibility into why candidate backends were selected or bypassed (e.g. whether a backend was penalized by urgency, quota cooldown, or conservation state), defeating the core design principle of *explainable routing*.
* **Recommended Fix:**  
  Emit a structured event before returning from `_select_candidate_backend`:

  ```python
  logger.info(
      "routing_decision",
      model=model,
      selected_backend=backend_id,
      operation=operation,
      candidates=[
          {
              "backend_id": b_id,
              "score": score,
              "weight": weight,
              "state": snapshots[b_id].state,
          }
          for score, weight, b_id in scored_candidates
      ],
      estimated_cost_usd=estimate.estimated_cost_usd,
  )
  ```

---

#### 4. `credit.py` Test Coverage Below Required 80% and Missing Dedicated Unit Test Suite

* **Severity:** **Major**
* **File/Module:** [`src/foundry_router/credit.py`](../../src/foundry_router/credit.py) & [`tests/unit/test_credit.py`](../../tests/unit)
* **The Issue:**  
  `src/foundry_router/credit.py` contains 280 statements with 82 missed lines, achieving only **70.71% test coverage**. This violates the repository rule in [`AGENTS.md`](../../AGENTS.md) requiring at least 80% coverage. Furthermore, there is no dedicated [`tests/unit/test_credit.py`](../../tests/unit) file.  
  Critical domain calculations currently lack tests:
  * Calendar boundary and leap year rollovers (`calculate_cycle_window` in Feb 28/29, month 12->1 transition, `now_utc` without tzinfo).
  * Array and nested dictionary traversal in token estimation (`_walk_text_chars`, `_estimate_embeddings_tokens`).
  * Response usage JSON extraction with `prompt_tokens`, `completion_tokens`, malformed non-JSON bytes, and negative usage values.
  * Cycle rollover in `_rollover_if_needed` when calendar cycle advances.
  * Composite scoring weight combinations and conservation thresholds.
* **Why Static Analysis Missed It:**  
  SonarQube and standard linters check overall workspace line counts if configured with broad exclusions, but unit test gaps on newly added modules require targeted coverage verification.
* **Impact:**  
  Undetected bugs in calendar arithmetic, leap year handling, token estimation, or usage parsing could cause silent financial reserve miscalculations in production.
* **Recommended Fix:**  
  Create [`tests/unit/test_credit.py`](../../tests/unit/test_credit.py) with comprehensive test cases targeting all credit calculations, cycle rollovers, token bounds, and response usage parsing to bring `credit.py` coverage well above 90%.

---

#### 5. Repeated JSON Deserialization and Validation in Request Hot Path

* **Severity:** **Major**
* **File/Module:** [`src/foundry_router/main.py:1038-1081`](../../src/foundry_router/main.py#L1038-L1081) & [`src/foundry_router/config/__init__.py:193-350`](../../src/foundry_router/config/__init__.py#L193-L350)
* **The Issue:**  
  `load_settings()` is called repeatedly across the execution of a single incoming request (in endpoint routing, auth validation, backend client lookups, and credit synchronization). Each call instantiates a new `Settings` object, triggering full JSON deserialization (`json.loads`) and Pydantic model validation for backends, models, pricing, cycle days, and API keys.
* **Why Static Analysis Missed It:**  
  Instantiation of configuration classes is syntactically standard and static tools cannot assess per-request allocation overhead.
* **Impact:**  
  Significant CPU overhead and garbage collection pauses under high concurrent request volumes, degrading proxy latency.
* **Recommended Fix:**  
  Use `functools.lru_cache` on `load_settings()` or initialize settings during application lifespan and inject it as a FastAPI dependency.

---

#### 6. Streaming Usage Extraction from Final Chunk Not Implemented

* **Severity:** **Suggestion**
* **File/Module:** [`src/foundry_router/main.py:832-860`](../../src/foundry_router/main.py#L832-L860)
* **The Issue:**  
  When OpenAI/Azure OpenAI streaming emits token usage in the terminal chunk (e.g. `stream_options: {"include_usage": true}`), `_stream_response` passes raw bytes through and finalizes the reservation with `charged_cost_usd=None, charge_reserved=True`. This charges the full 4,096-token default estimate even for a 20-token streaming response.
* **Why Static Analysis Missed It:**  
  The streaming generator faithfully streams bytes; payload parsing during SSE generator iteration is a domain-specific optimization.
* **Impact:**  
  Short streaming responses will over-penalize estimated backend remaining balances until the monthly cycle rolls over.
* **Recommended Fix:**  
  Inspect SSE events in the generator for terminal usage payloads (or parse data lines before yielding) to pass the exact `charged_cost_usd` to `finalize_request`.

---

#### 7. Redundant Pre-Validation Model Check

* **Severity:** **Suggestion**
* **File/Module:** [`src/foundry_router/main.py:1039, 1082`](../../src/foundry_router/main.py#L1039)
* **The Issue:**  
  `create_response` and `create_embeddings` invoke `_select_backend(settings, body["model"])` solely to return 404 for unknown models, before delegating to `_execute_with_single_failover` which performs candidate selection with `_select_candidate_backend`.
* **Recommended Fix:**  
  Directly check `if body["model"] not in settings.models: return _api_error(404, f"Model '{body['model']}' not found", "model_not_found")`.

---

### Verification Summary

- **Current Test Suite:** 119 unit/integration tests passing.
* **Overall Codebase Coverage:** 82.76%.
* **Module Coverage Gap:** `src/foundry_router/credit.py` is at **70.71%** (needs dedicated `test_credit.py` to reach ≥80%).
* **Security Posture:** Clean HMAC constant-time auth checks, SSRF prevention with HTTPS/host allow-lists, strict header sanitization, and structured log redaction remain intact.
