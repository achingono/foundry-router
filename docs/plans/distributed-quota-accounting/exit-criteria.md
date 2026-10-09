# Quota exit criteria

- [x] Independent plan review cleared before implementation.
- [ ] Atomic full-group admission caps across independent stores; no replica division.
- [ ] Durable minute/day accounting, restart and idempotent settlement/release.
- [ ] Unknown expiry/ambiguous writes retain usage and prevent alternate dispatch.
- [ ] Bounded rows/records/retries and drained fingerprint changes verified.
- [ ] Clock/skew/Pacific/DST assumptions and conservative behavior verified locally.
- [ ] Configuration/startup/readiness/admin and old memory behavior verified.
- [ ] Real local Azurite concurrency/persistence passed.
- [ ] Full coverage ≥80%, style/types/Docker/contextual review/docs checks passed.
- [ ] Evidence and transition committed; production remains memory/one.
