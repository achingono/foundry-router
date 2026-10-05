# Risks

| ID | Risk | Impact | Mitigation | Status |
|---|---|---|---|---|
| R1 | Provider API mismatch | Requests fail | Exact observed diagnostics, bounded probe | Open |
| R2 | Output/secret leakage | Sensitive logs | Metadata-only output, captured auth and errors | Open |
| R3 | Unexpected credit charge | Test budget use | Four bounded initial requests; test prices labeled | Open |
| R4 | Truncated streaming or reservations leak | Incorrect reconciliation | Terminal event/usage and admin checks | Open |
