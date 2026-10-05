# Risks

| ID | Risk | Impact | Mitigation | Status |
|---|---|---|---|---|
| R1 | Wrong subscription grant scope | Image pull fails | Explicit subscription/RG lookup and scoped grant | Open |
| R2 | Production credit double counted | Over-admission | Canonical two-group runtime diagnostics | Open |
| R3 | Auth overwritten or exposed | Client break/leak | Generate once, captured keys and namespaced vault | Open |
| R4 | Memory state lost on restart | Estimate resets | Document starting estimate/reconciliation and one-replica constraint | Open |
| R5 | Model listing mistaken for live inference | Overclaim | Config-only smoke; production inference separate | Open |
