# Phase 04 Hardening Activities

## Step-By-Step Activities

1. **Defensive SSE Buffer Limiting**:
   - Introduce `MAX_SSE_EVENT_BUFFER_BYTES = 128 * 1024` (128 KB) in streaming generators.
   - If an upstream backend emits unbounded bytes without delimiter `\n\n`, flush safely, log a warning, and prevent memory exhaustion.

2. **Edge-Case Reservation Lifecycle Verification**:
   - Add unit tests verifying `try...finally` cleanup when `asyncio.CancelledError` occurs at various stages (before first byte, mid-stream, during failover selection).
   - Test non-2xx status code matrix (4xx/5xx) to guarantee zero credit debit for non-successful upstream responses.

3. **Terminal SSE Usage Parsing Edge Cases**:
   - Test malformed JSON, truncated chunks, interleaved keep-alive comments (`: keep-alive`), and usage payloads split across multiple chunk boundaries.

4. **Coverage and Quality Gating**:
   - Verify `credit.py` coverage exceeds 90% and repository coverage exceeds 85%.
   - Run type checks (`mypy`), linting, and formatting (`ruff`).

## Review Focus
- Memory bounding during high-volume streaming responses.
- In-flight credit reservation invariants under abnormal termination.
- Zero-charge behavior on upstream rejections.
