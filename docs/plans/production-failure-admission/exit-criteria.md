# Exit Criteria

## Gate Checklist

- [x] Independent plan approval recorded before live traffic.
- [x] Read-only baseline (live/ready/models/admin/metrics) captured; readiness healthy at start and end.
- [x] Each admission probe returned its documented status/type with no attributed backend egress and zero active/inflight reservations after (except pre-specified `previous_response_id` candidate, which returned provider-attributed 400 with zero-charge settlement; recorded explicitly).
- [x] At most two `fs-swarm`-pool inference requests sent (pinned `gpt-6-luna`); both settled with terminal usage, usage-matched local estimated debit, no partial trailing frame, and zero inflight/active reservations.
- [x] No retry after streaming output began; no induced 429/5xx or exhaustion probe performed.
- [x] Temporary vault access removed (none created — direct reads succeeded; temp files deleted); production config/image/secrets/tables/grants/ingress/replicas unchanged; production still memory/one.
- [x] Evidence/review/links complete with explicit routing scope (both test dispatches served by the `fs-openclaw` backend for the pinned pool); remaining `fs-openclaw`, live upstream 429/5xx failover, Table/embeddings/cost gates listed as still unverified.
- [x] No prompts, outputs, credentials, subscription IDs, endpoints, or deployment IDs retained in docs or logs.

## Approval Table

| Role | Name | Status | Notes |
|---|---|---|---|
| Owner | implementing session | Complete | Live run executed within bounds; evidence recorded |
| Reviewer | independent session | Approved with findings | 1 Major + 4 Minor, all doc-clarifications applied before live traffic |
| Approver | operator | Approved | Authorized fs-swarm-pool scope, cheapest-pool pinning, no embeddings; supplied FQDN at runtime |
