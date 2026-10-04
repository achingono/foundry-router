# Module Extraction Risk Register

## Risks
| ID | Risk | Impact | Mitigation | Status |
|---|---|---|---|---|
| R1 | Identity outputs alter GUIDs or ordering | Role conflicts | Equivalent static ID and runtime principal; ARM reviewed | Mitigated |
| R2 | Workspace key reference before creation | Environment fails | Explicit observability dependency; redeployment verified | Mitigated |
| R3 | Plan resource blocks fresh bootstrap | Environment cannot ingest | Retain documented first-pass bootstrap false | Mitigated |
| R4 | Secrets in module outputs | Credential exposure | Only non-secret refs; root key lookup reviewed | Mitigated |

## Open Decisions
- Further environment/workload/resource extraction remains Design target after this increment.
