# Risks

| Risk | Mitigation | Status |
| --- | --- | --- |
| Catalog doesn't prove account/model live compatibility | Exact bounded staging gates, halt without replay | Open |
| Claude uses different wire | Separate bounded nonstream provider; reject streaming/tools/thinking before admission | Open |
| Cache usage/refusal/protocol failure undercharges | Independent usage capture; cache-inclusive input pricing; conservative failure settlement | Open |
| Memory restart duplicates/replenishes credit | Quietness/drain/stopped writers/fresh all-account seed | Open |
| Grok/Google thinking consumes bound without text |512 token bound, low Google profile; thinking-only cannot pass | Open |
| Current allocation binding |10USD and0.05/5reserve confirmed; staged .10USD suballocation, production9.90USD conservative seed | Mitigated |
