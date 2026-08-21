# Phase 01 Hardening Risk Register

## Risks
| ID | Risk | Impact | Mitigation | Status |
| --- | --- | --- | --- | --- |
| R1 | Tightening URL validation breaks existing test fixtures | Test and local development failures | Use explicit HTTPS test origins and test transports; never weaken production validation | Mitigated by plan |
| R2 | Exception sanitization hides useful diagnostics | Slower incident diagnosis | Log stable error type, operation, and correlation ID; retain detailed diagnostics only in approved redacted channels | Open |
| R3 | Docker smoke configuration appears production-like | Accidental use of test values | Keep smoke values clearly synthetic and document that no upstream calls are made | Open |
| R4 | JSON configuration remains difficult to author in dotenv | Startup errors for operators | Use one-line quoted examples and add format documentation | Mitigated by plan |
| R5 | Exact path validation conflicts with future backend API path construction | Requests rejected or duplicated paths | Normalize endpoint base paths and define one owning boundary for path joining | Open |

## Open Decisions
- Whether a future release should support a separate structured JSON settings file instead of large dotenv values.
- Whether future redirect support should validate each hop or remain disabled permanently.
