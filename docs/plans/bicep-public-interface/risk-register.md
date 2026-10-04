# Public Interface Risk Register

| ID | Risk | Impact | Mitigation | Status |
|---|---|---|---|---|
| R1 | Invalid union branch access | Template failure | Guarded access and schema/Azure validation passed | Mitigated |
| R2 | Nested scope/name changes | Role/resource drift | Same RG mapping reviewed; typed redeployment passed | Mitigated |
| R3 | Flat defaults lost | Behavior drift | All mapped/shared defaults verified | Mitigated |
| R4 | Credentials in typed config | Exposure | Separate secureString parameter reviewed | Mitigated |
