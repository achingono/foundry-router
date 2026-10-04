# Risks

| ID | Risk | Impact | Mitigation | Status |
|---|---|---|---|---|
| R1 | Public load balancing hides replica identity | False shared-state proof | Targeted exec and local app diagnostics verified | Mitigated |
| R2 | Replica exec/restart unsupported | Gate cannot be proven | PTY exec and targeted PID1 termination verified; throttle respected | Mitigated |
| R3 | Verification mutates credit | Synthetic state drift | Isolated partition removed; estimate restored/reservation released | Mitigated |
| R4 | Shared environment changes | Baseline regression | Same configuration; original baseline smoke passed | Mitigated |
