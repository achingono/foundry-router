# Production inference verification

## Status: Implemented

Verify each of the six configured production model pools with one non-streaming and one streaming Responses request. Production remains memory-backed with one replica; this test does not establish every individual backend's inference or provider failure behavior.

All 12 requests completed with HTTP200 and usage-matched shared-account debits. Counters identify fs-swarm as the selected resource for every request; fs-openclaw inference and provider failover remain unverified.

- [Inputs](inputs.md)
- [Activities](activities.md)
- [Outputs](outputs.md)
- [Exit criteria](exit-criteria.md)
- [Risks](risk-register.md)
- [Evidence](evidence.md)
