# Phase 07 Risk Register

## Risk Assessment

| Risk ID | Description | Impact | Likelihood | Mitigation |
|---|---|---|---|---|
| R-P07-01 | Container shutdown kills active streams prematurely | Medium | Medium | Implement bounded graceful shutdown drain period (10s) in lifespan handler. |
| R-P07-02 | Unbounded connection pool exhausts OS file descriptors | High | Low | Enforce explicit connection and keep-alive limits via `httpx.Limits`. |
