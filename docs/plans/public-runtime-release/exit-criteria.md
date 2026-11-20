# Public runtime release exit criteria

- [x] Focused and full applicable tests pass with runtime coverage at least 80%.
- [x] Lint, formatting, types and changed-document links pass; inherited historical link failures are recorded.
- [x] Docker/Linux checks pass or accepted exact build-input equivalence is recorded.
- [x] Runtime contents match the reviewed source exactly.
- [x] All outgoing commits exclude private operational data and dependencies.
- [ ] A separate reviewer accepts the frozen candidate and ancestry before publication.

Deployment requires separate environment-specific acceptance; local tests do not establish Azure capacity, ingestion, provider compatibility or scale readiness.
