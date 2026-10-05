# Risks

| ID | Risk | Impact | Mitigation | Status |
|---|---|---|---|---|
| R1 | Key exposed | Credential leak | Captured CLI response, vault HTTPS, redacted output | Open |
| R2 | Per-deployment estimates treated as shared resource credit | Misleading balance | Explicit test-only per-backend accounting, no authoritative claims | Open |
| R3 | Synthetic config overwritten | Test regression | Dedicated secret prefix/app and generated auth keys | Open |
| R4 | Readiness mistaken for inference success | Overclaim | No inference in this phase; explicit pending scope | Open |
