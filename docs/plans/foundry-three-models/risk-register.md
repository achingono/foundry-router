# Foundry three-model risks

| Risk | Mitigation |
| --- | --- |
| Anthropic cache-write costs exceed ordinary input | Cache-inclusive token totals, configured conservative write/input ceiling, no inferred read discount in first adapter scope. |
| MAI bills per image but exposes no token usage | Reserve and settle exactly one configured positive image ceiling, retain it on ambiguous/malformed post-dispatch results; never infer free output from absent token usage. |
| PNG size/expansion or transport overload | Existing bounded Linux PNG worker, one image, finite response and delivery limits, request-owned inspection lease. |
| Protocol mismatch silently forwards unsupported input | Dedicated providers, exact nonstream contract, explicit operation/config gates, no raw fallback. |
| Restart resurrects old memory credit | Deny/drain/final process snapshot, frozen seed evidence, exclude old writers, pin coherent image/config. Archive cumulative counters before memory counters reset. |
| Acceptance retry/failover exceeds spend bound | Translated providers single-attempt/only safe 429 handling; budget every possible Terra upstream attempt and MAI candidate. Consume slots before dispatch, no blind replay. |
| Public prices lag new model release | Do not activate unpriced metered model; query retail/historical/provider documentation and record verified source. |
