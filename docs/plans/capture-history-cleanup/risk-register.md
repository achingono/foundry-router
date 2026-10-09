# Capture cleanup risk-register

## Risks
| Risk | Mitigation |
| --- | --- |
| Indirect tests require captures | Trace file reads plus static inspection; verify clean checkout. |
| Ignored local files mask dependency | Run all offline tests from tracked-only checkout before rewrite. |
| Broken evidence links | Mark removed artifacts local-only and keep Markdown summaries. |
| Lost artifacts/history | Preserve hashes and owner-only ignored recovery bundle. |
