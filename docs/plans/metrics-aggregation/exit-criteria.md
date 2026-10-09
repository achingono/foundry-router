# Metrics exit criteria

- [x] Independent plan review cleared before runtime changes.
- [x] Exact SDK/exporter pinned, endpoint/auth/retry/redirect bounds verified.
- [x] Default Prometheus/auth behavior unchanged; live startup proxy wiring verified.
- [x] Two independent worker identities, counters/cost/exclusions/histograms verified.
- [x] Actual subprocess receiver and restart aggregate totals without duplicate snapshots.
- [x] Failure isolation, secret redaction and bounded flush/thread shutdown passed.
- [x] Full coverage≥80%, style/types/Docker/contextual review/docs checks passed.
- [x] Transition committed; deployed collector/provider acceptance remains gated.
