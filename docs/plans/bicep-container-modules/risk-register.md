# Container Modules Risk Register

## Risks
| ID | Risk | Impact | Mitigation | Status |
|---|---|---|---|---|
| R1 | Runtime identity object not deployment-start evaluable | BCP120 | Separate identity ID param compiled/deployed successfully | Mitigated |
| R2 | Lost grants dependency | Pull/secret/state failures | Same compiled workload dependency set confirmed | Mitigated |
| R3 | Password crosses plain object boundary | Credential exposure | Separate secureString module param reviewed | Mitigated |
| R4 | Secret/runtime mapping changes | Startup drift | Explicit URLs and exact payload equivalence reviewed | Mitigated |

## Open Decisions
- Registry/vault extraction and public discriminated deployment API remain Design target.
