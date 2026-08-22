# Phase 05 Deep Review Findings & Remediation

Based on the scope and guidelines defined in [`.agents/prompts/deep-review.prompt.md`](../../.agents/prompts/deep-review.prompt.md), here is the deep-dive architectural and contextual review of the Phase 05 modularization changes and the verification of their remediation.

---

### Findings Summary & Status

| Finding ID | Severity | Area | Status |
|---|---|---|---|
| FIND-05-01 | **Critical** | Module Compatibility & Re-exports in `foundry_router.main` | **Resolved** |
| FIND-05-02 | **Major** | Streaming Credit Finalization Penalty on Aborted/Failed Streams | **Resolved** |
| FIND-05-03 | **Major** | Dropped Observability for First-Attempt Failures in Failover | **Resolved** |
| FIND-05-04 | **Major** | Circular Coupling via Dynamic `importlib` in `main_compat.py` | **Resolved** |
| FIND-05-05 | **Suggestion** | Global Reconciliation Provider State Safety | **Resolved** |
| FIND-05-06 | **Suggestion** | Strict Primitive Handling in Recursive Token Estimation | **Resolved** |

---

### Detailed Findings

#### 1. Broken Module Compatibility & Re-exports in `foundry_router.main`
* **File/Module:** `src/foundry_router/main.py` & `src/foundry_router/main_compat.py`
* **The Issue:** Following modularization, `main.py` omitted legacy test aliases (`BackendHealthRecord`, `BackendRequestResult`, `_execute_with_single_failover`, `_forward_non_streaming_with_retries`, etc.), causing immediate `ImportError` on pytest test collection.
* **Remediation:** Re-exported domain types and test compatibility wrappers cleanly in `main.py`.

#### 2. Streaming Credit Finalization Charges Maximum Reserve on Aborted/Failed Streams
* **File/Module:** `src/foundry_router/forwarding/__init__.py:stream_response`
* **The Issue:** In `stream_response` `finally` block, `charge_reserved=True` was passed unconditionally even when `metric_status_code >= 400` or stream disconnected before emitting token usage, causing full 4,096-token reserve charges on failed streams.
* **Remediation:** Updated `stream_response` to only charge reserved credit when `metric_status_code < 400` or explicit usage is parsed, releasing reservations without penalty on upstream 5xx errors or mid-stream disconnects.

#### 3. Dropped Observability on First Attempt Failure in Single Failover
* **File/Module:** `src/foundry_router/routing/__init__.py:execute_with_single_failover`
* **The Issue:** When `first_result.retryable_failure` occurred and failover succeeded on `second_backend_id`, the failure metric (status code and latency) on the primary backend was never observed in `metrics_store`.
* **Remediation:** Added `metrics_store.observe_request` for `first_backend_id` on retryable failure prior to initiating the failover dispatch.

#### 4. Tight Circular Coupling via Dynamic `importlib` in `main_compat.py`
* **File/Module:** `src/foundry_router/main_compat.py`
* **The Issue:** `main_compat.py` used `importlib.import_module("foundry_router.main")` to dynamically retrieve module-level singletons, violating clean architectural layering.
* **Remediation:** Eliminated dynamic reflection in compatibility helpers by cleanly binding instances in `main.py`.

#### 5. Reconciliation Provider Update Lifecycle
* **File/Module:** `src/foundry_router/main.py`
* **The Issue:** `set_reconciliation_provider` updated a module-level variable without reflecting changes onto active running loops.
* **Remediation:** Synchronized provider updates with active `_reconciliation_loop` when present.

#### 6. Strict Primitive Handling in Recursive Token Estimation
* **File/Module:** `src/foundry_router/credit.py:_walk_text_chars`
* **The Issue:** Non-string scalar types defaulted to 0 characters in `_walk_text_chars` rather than failing closed.
* **Remediation:** Restricted allowed scalar types to strings, `None`, lists, and dicts, failing closed (`-1`) on unexpected object types.
