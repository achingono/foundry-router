# Metrics exit criteria

- [x] Independent plan review cleared before runtime changes.
- [ ] Exact SDK/exporter pinned, endpoint/auth/retry/redirect bounds verified.
- [ ] Default Prometheus/auth behavior unchanged; live startup proxy wiring verified.
- [ ] Two independent worker identities, counters/cost/exclusions/histograms verified.
- [ ] Actual subprocess receiver and restart aggregate totals without duplicate snapshots.
- [ ] Failure isolation, secret redaction and bounded flush/thread shutdown passed.
- [ ] Full coverage≥80%, style/types/Docker/contextual review/docs checks passed.
- [ ] Transition committed; deployed collector/provider acceptance remains gated.
