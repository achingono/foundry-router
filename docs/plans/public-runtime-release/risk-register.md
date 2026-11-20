# Public runtime release risks

| Risk | Mitigation |
| --- | --- |
| Publication includes environment-specific records | Export an explicit allowlist from Git objects and inspect all outgoing commits |
| Public tests silently use another checkout | Set PYTHONPATH to this candidate and scope coverage to its runtime directory |
| Optional intake exceeds worker capacity | Keep default-off until full-runtime capacity and ingress acceptance pass |
| Completion console writes are mistaken for ingestion | Require destination completeness and loss-counter checks before rollout acceptance |
| Automation bypasses ledger preservation | Production dispatch is guarded; use reviewed maintenance and preserve authoritative Table state |
