# Production Rollout Exit Criteria

- [x] Independent plan review complete and findings addressed.
- [x] Manifest-verified release passed ACR unit/integration/Azurite/coverage/lint/type checks, Docker build/image smoke and template checks; GitHub CI separately unpassed.
- [x] Production image/aliases deployed with memory state, maxReplicas=1 and ingress unchanged, using fresh pinned initial estimates.
- [x] Health/auth/catalog/admin checks passed with exact alias targets.
- [x] Six distinct direct/aliased normal and streaming inference cases passed with canonical metric accounting.
- [x] Actual approval client passed synthetic allow, deny and injected error cases without policy changes.
- [x] Evidence, operational status and rollback guidance updated; no prompts, outputs or secret values retained.

Exact credit continuity during the unfenced memory rollout is not established. Concurrent requests prevent attribution of every total-balance change. GitHub CI remains separately unpassed; Table production cut-over is outside this rollout.
