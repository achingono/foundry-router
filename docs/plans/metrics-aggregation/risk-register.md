# Metrics risks

| Risk | Mitigation | Status |
| --- | --- | --- |
| Repeated cumulative samples double counted | Preserve resource lifetime ID; sum rate/delta per identity | Open |
| Worker restart merges counter lifetimes | Generated process-lifetime resource ID | Open |
| Shared account/quota gauges summed | Keep snapshots local and document nonadditive aggregation | Open |
| Telemetry failure blocks settlement | Periodic reader/off-hotpath, isolated observation failure | Open |
| Exporter follows redirects/leaks auth or retries unbounded | Inspect official transport, confined session and dispatch tests | Open |
| Shutdown leaves threads/tasks | Bounded reader flush/shutdown, real subprocess verification | Open |
| Local evidence mistaken for Azure readiness | Separate collector/network/deployment acceptance gates | Open |
