# Quota exit criteria

- [x] Independent plan review cleared before implementation.
- [x] Atomic full-group admission caps across independent stores; no replica division.
- [x] Durable minute/day accounting, restart and idempotent settlement/release.
- [x] Unknown expiry/ambiguous writes retain usage and prevent alternate dispatch.
- [x] Bounded rows/records/retries and drained fingerprint changes verified.
- [x] Clock/skew/Pacific/DST assumptions and conservative behavior verified locally.
- [x] Configuration/startup/readiness/admin and old memory behavior verified.
- [x] Real local Azurite concurrency/persistence passed.
- [x] Full coverage ≥80%, style/types/Docker/contextual review/docs checks passed.
- [x] Evidence and transition committed; production remains memory/one.
