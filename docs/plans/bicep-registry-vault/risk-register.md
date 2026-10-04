# Registry/Vault Risk Register

## Risks
| ID | Risk | Impact | Mitigation | Status |
|---|---|---|---|---|
| R1 | Grant GUID changes | Conflicts | Equivalent arguments/order and literals confirmed | Mitigated |
| R2 | Disabled new-module output reference | Memory/external deployment fails | Guards reviewed; mode matrix and what-if passed | Mitigated |
| R3 | Module completion changes pull/secret order | Startup failures | Complete provisioning/grant dependencies verified | Mitigated |
| R4 | Existing shared parent mutated | Operational drift | Existing scopes/modules unchanged and baseline redeployed | Mitigated |

## Open Decisions
- A public discriminated deployment entry point remains Design target; flat compatibility interface stays public.
