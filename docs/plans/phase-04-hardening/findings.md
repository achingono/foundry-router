### Deep Review Findings

#### 1. Staleness False-Negative on Continuous Startup Failures
* **File/Module:** [`src/foundry_router/reconciliation/__init__.py`](file:///Users/achingono/source/repos/foundry-router/src/foundry_router/reconciliation/__init__.py#L124-L134)
* **The Issue:** `ReconciliationLoop._is_stale()` returns `False` whenever `last_success_utc` is `None`. If the reconciliation loop fails repeatedly starting from container boot (due to network partition, bad provider credentials, or upstream downtime), the router will perpetually report `"stale": false` in `/admin/status` diagnostics despite running for hours on un-reconciled, drifting local estimates.
* **Why Static Analysis Missed It:** Static analyzers check for `None` safety and correct type returns (`bool`), but cannot infer the semantic business rule that absence of any success over multiple polling intervals constitutes stale state.
* **Impact:** Monitoring and alerting systems consuming `/admin/status` will report healthy reconciliation status even when the router has never successfully reconciled with the billing source.
* **Recommended Fix:** Account for elapsed time since initialization or consecutive failure count when `last_success_utc` is `None`:
```python
def _is_stale(self) -> bool:
    stale_after = max(1, int(self._settings.reconciliation_interval_minutes) * 60 * 2)
    if self._status.last_success_utc is None:
        # If we have attempted and failed, or have never succeeded after multiple intervals
        return self._status.consecutive_failures > 0 or self._status.last_attempt_utc is not None
    try:
        last_success = datetime.fromisoformat(self._status.last_success_utc)
    except ValueError:
        return True
    age_seconds = (datetime.now(UTC) - last_success).total_seconds()
    return age_seconds > stale_after
```

---

#### 2. Risk of Credential / Secret Leakage in Raw Provider Exception Logging
* **File/Module:** [`src/foundry_router/reconciliation/__init__.py`](file:///Users/achingono/source/repos/foundry-router/src/foundry_router/reconciliation/__init__.py#L95-L105)
* **The Issue:** In `run_once()`, provider exceptions are caught and logged with `message=str(exc)`. For HTTP-based or SDK-based reconciliation providers (e.g., Azure Cost Management, ARM REST calls), `str(exc)` often contains full request URLs with SAS tokens, client query parameters, or authorization header excerpts.
* **Why Static Analysis Missed It:** Linters and static scanners look for hardcoded strings or variables explicitly named `token`/`password`/`key`, but cannot detect dynamically formatted exception message strings from third-party client libraries.
* **Impact:** Violates the core security requirement to never log credentials, API keys, or raw tokens in structured logs.
* **Recommended Fix:** Omit raw unredacted `str(exc)` from the structured log event, or restrict it strictly to sanitized/redacted diagnostics:
```python
except Exception as exc:
    self._status.consecutive_failures += 1
    self._status.last_error = type(exc).__name__
    self._status.last_updated_backends = 0
    self._logger.warning(
        "credit_reconciliation_unavailable",
        error_type=type(exc).__name__,
        consecutive_failures=self._status.consecutive_failures,
    )
    return
```

---

#### 3. Synchronous Blocking `run_once()` in Application Lifespan Startup
* **File/Module:** [`src/foundry_router/main.py`](file:///Users/achingono/source/repos/foundry-router/src/foundry_router/main.py#L1045-L1052) & [`src/foundry_router/reconciliation/__init__.py`](file:///Users/achingono/source/repos/foundry-router/src/foundry_router/reconciliation/__init__.py#L70-L76)
* **The Issue:** `lifespan()` awaits `_reconciliation_loop.start()`, which in turn awaits `self.run_once()`. If an external billing provider experiences high latency or hangs on TCP connect during startup, FastAPI startup will block and fail Kubernetes/container readiness and liveness probes before the router can serve traffic from its initial local settings snapshot.
* **Why Static Analysis Missed It:** Awaiting an async method inside an async lifespan handler is syntactically and structurally valid async code.
* **Impact:** Startup dependency coupling: slow external billing APIs can prevent the proxy from booting or recovering, contradicting the requirement that reconciliation is best-effort and non-blocking.
* **Recommended Fix:** Launch the periodic reconciliation task in the background without blocking the lifespan startup sequence, or bound the initial run with a strict startup timeout:
```python
async def start(self) -> None:
    if self._task is not None and not self._task.done():
        return
    self._stop_event.clear()
    self._task = asyncio.create_task(self._run(), name="credit-reconciliation")
```

---

#### 4. Module Test Coverage Gate Breach (68.49%)
* **File/Module:** [`src/foundry_router/reconciliation/__init__.py`](file:///Users/achingono/source/repos/foundry-router/src/foundry_router/reconciliation/__init__.py) & [`tests/unit/test_reconciliation.py`](file:///Users/achingono/source/repos/foundry-router/tests/unit/test_reconciliation.py)
* **The Issue:** `test_reconciliation.py` only executes `run_once()` on stub objects. `start()`, `stop()`, background loop execution `_run()`, and staleness calculation `_is_stale()` are untested, bringing module coverage to 68.49%, below the repository's required 80% threshold (`AGENTS.md` Rule 5).
* **Why Static Analysis Missed It:** Unit test runners verify test pass/fail; coverage threshold validation only fails if enforced per-module in the CI pipeline.
* **Impact:** Critical lifecycle bugs (e.g. task cancellation leaks, uncaught loop errors, staleness detection bugs) can escape into production undetected.
* **Recommended Fix:** Add unit tests in `tests/unit/test_reconciliation.py` covering:
  - `start()` and `stop()` lifecycle, ensuring clean shutdown without task leaks.
  - Periodic trigger via `_run()` with short timeouts.
  - Staleness evaluation when timestamps are fresh, expired, invalid, and empty.

---

#### 5. Documentation Table Column Separator Syntax Mismatch
* **File/Module:** [`docs/decisions/requirements-traceability.md`](file:///Users/achingono/source/repos/foundry-router/docs/decisions/requirements-traceability.md#L28-L30) & [`docs/decisions/requirements-traceability.md`](file:///Users/achingono/source/repos/foundry-router/docs/decisions/requirements-traceability.md#L73-L75)
* **The Issue:** 
  - Line 28 has 3 column headers (`Requirement`, `Implementation`, `Evidence`), but line 29 separator defines 4 columns (`| --- | --- | --- | --- |`).
  - Line 73 has 4 column headers (`Requirement`, `Implementation Status`, `Package`, `Evidence`), but line 74 separator defines 3 columns (`| --- | --- | --- |`).
* **Why Static Analysis Missed It:** Markdown linters without strict table formatting rules do not catch column delimiter count mismatches.
* **Impact:** Markdown rendering engines (e.g. GitHub, MkDocs) will produce malformed HTML tables.
* **Recommended Fix:** Align the separator bar count with the header column count across all tables in `requirements-traceability.md`.