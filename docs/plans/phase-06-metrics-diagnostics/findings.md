# Deep Review Report

Based on the scope and guidelines defined in [`.agents/prompts/deep-review.prompt.md`](.agents/prompts/deep-review.prompt.md), here is the deep-dive architectural and contextual review of the current changes.

---

### Critical Findings

* **File/Module:** [`src/foundry_router/metrics/__init__.py`](src/foundry_router/metrics/__init__.py#L26-L115) (`InMemoryMetricsStore.observe_request` and `InMemoryMetricsStore.render_prometheus`)
* **The Issue:** **Double-accumulation in Prometheus histogram rendering.**
  In `observe_request`, for each request with latency $L$, the method iterates over `LATENCY_BUCKETS_SECONDS` and increments every bucket where $L \le \text{bucket}$. Consequently, `self._latency_bucket_counts` stores **already cumulative** counts. In `render_prometheus`, it loops over the buckets again and executes `cumulative += latency_buckets.get(...)`, summing the already-cumulative bucket counts.
* **Why Static Analysis Missed It:** Both methods are fully type-annotated, thread-safe, and syntactically sound. Static analyzers and simple unit tests asserting string presence (`"foundry_router_latency_seconds_bucket" in body`) do not evaluate mathematical monotonicity or check that finite bucket sums must not exceed the `+Inf` total count.
* **Impact:** Distorts Prometheus histogram data in production. For example, a single `0.01s` request records count `1` in bucket `0.05s`, `2` in `0.1s`, `3` in `0.25s`, ..., and `8` in `10.0s`, while `+Inf` reports `1`. Any Prometheus or Grafana `histogram_quantile()` query will yield invalid percentiles or negative quantile errors.
* **Recommended Fix:**
  Either record raw un-accumulated counts into discrete buckets in `observe_request` and accumulate during rendering, or store cumulative counts in `observe_request` and output them directly without re-accumulating.

```python
# Option A: Store discrete counts per bucket, accumulate only during rendering
async def observe_request(...):
    # Find matching bucket and increment only that bucket or +Inf
    async with self._lock:
        ...
        for bucket in LATENCY_BUCKETS_SECONDS:
            if latency_seconds <= bucket:
                self._latency_bucket_counts[(model, backend, bucket)] += 1
                break

# In render_prometheus:
cumulative = 0
for bucket in LATENCY_BUCKETS_SECONDS:
    cumulative += latency_buckets.get((model, backend, bucket), 0)
    lines.append(f'foundry_router_latency_seconds_bucket{{...,le="{bucket:g}"}} {cumulative}')
```

---

### Major Findings

* **File/Module:** [`src/foundry_router/main.py`](src/foundry_router/main.py#L447-L509) (`_record_and_return` and streaming response handling)
* **The Issue:** **Premature metrics recording for streaming responses.**
  `_record_and_return` records latency and HTTP status code at the moment the `StreamingResponse` object is generated.
  1. The recorded latency measures Time-To-First-Byte (TTFB) / header arrival rather than total stream duration or time-to-first-token.
  2. If the upstream stream fails or aborts mid-stream, the metric has already been recorded as a successful `200 OK`.
* **Why Static Analysis Missed It:** Returning `StreamingResponse` conforms to the FastAPI signature. Static analyzers cannot track asynchronous stream generators consumed after the route handler completes.
* **Impact:** Mid-stream disconnects and upstream failures are invisible in Prometheus request outcome counters, and stream latency metrics reflect only connection setup time (e.g., 2ms) rather than full stream durations (e.g., 10–30s).
* **Recommended Fix:**
  Hook the metrics observation into the completion/exception blocks of `_stream_response` generator, or expose two explicit metrics: `foundry_router_ttfb_seconds` and `foundry_router_streaming_duration_seconds`.

---

* **File/Module:** [`src/foundry_router/main.py`](src/foundry_router/main.py#L1295-L1319) (`GET /metrics` endpoint)
* **The Issue:** **Public unauthenticated exposure of operational and financial telemetry.**
  `GET /metrics` is exposed without authentication (`verify_admin_auth` or client authentication), exposing:
  - Internal backend pool IDs and Azure deployment topologies
  - Real-time spendable credit balances via `foundry_router_credit_available_usd`
  - Exact request throughput and error distributions
* **Why Static Analysis Missed It:** Declaring public routes without dependencies is valid FastAPI code. Static tools cannot judge the business sensitivity of exposed gauge metrics.
* **Impact:** If deployed in multi-tenant environments or at network boundaries, unauthorized parties can probe backend pool names, monitor traffic surges, and inspect remaining monetary credit balances.
* **Recommended Fix:**
  Protect `/metrics` with `dependencies=[Depends(verify_admin_auth)]` or a dedicated scraper token header to match `/admin/status`.

---

* **File/Module:** [`src/foundry_router/main.py`](src/foundry_router/main.py#L436-L458) (`_execute_with_single_failover` estimated cost metric)
* **The Issue:** **Metric cost overestimation on completed requests.**
  `_record_and_return` uses `estimated_request_cost_usd` (the conservative pre-request reservation calculated with default/maximum output tokens) instead of the actual finalized cost calculated in `_finalize_non_streaming_credit`.
* **Why Static Analysis Missed It:** The cost variable is validly typed and populated. Static analyzers cannot discern the semantic difference between pre-flight upper-bound reservations and post-flight actual usage.
* **Impact:** `foundry_router_estimated_cost_usd_total` diverges significantly from actual token costs (over-reporting cost by 5–10x for short responses with high `max_tokens` limits).
* **Recommended Fix:**
  Pass the finalized cost from `_finalize_non_streaming_credit` to the metrics observer on request completion.

---

### Suggestions & Technical Debt

* **File/Module:** [`src/foundry_router/main.py`](src/foundry_router/main.py#L468-L600) (`_execute_with_single_failover`)
* **The Issue:** **Structural duplication in metrics recording across exit branches.**
  `_record_and_return` is manually awaited across 9 distinct return branches in `_execute_with_single_failover`.
* **Why Static Analysis Missed It:** Each call is syntactically valid and returns the expected type.
* **Impact:** High cognitive overhead and risk that future failover branches or error paths will omit metrics observation.
* **Recommended Fix:**
  Encapsulate request execution and metric recording inside an async context manager or try/finally wrapper within `_execute_with_single_failover`.