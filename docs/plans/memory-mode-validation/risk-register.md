# Memory-mode Validation Risk Register

## Risks

| ID | Risk | Impact | Mitigation | Status |
|---|---|---|---|---|
| R1 | Conditional scoped roles introduce invalid ARM references | Memory deployment fails | Entire new-storage branch isolated; Azure validation passed | Resolved |
| R2 | Shared vault is empty or write access unavailable | App cannot initialize | Tenant mismatch found; approved dedicated vault used | Resolved |
| R3 | Changing role GUIDs duplicates assignments | Deployment conflict | Original GUID inputs preserved and independently reviewed | Mitigated |
| R4 | Smoke script mishandles shell quoting or retries | Misleading checks | Used direct bounded HTTP checks; script repair remains separate | Mitigated |
| R5 | Shared-resource mutation or synthetic baseline overclaim | Operational drift | Shared settings preserved; synthetic scope explicitly recorded | Mitigated |

## Open Decisions
- Real inference and Table runtime checks remain separate gates.
- Azure extras lack aiohttp in the current package declaration; installed locally for verification. Table image readiness must address this before cut-over.
