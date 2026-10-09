# Envelope Risks

| Risk | Mitigation |
| --- | --- |
| Provider state disclosure | Allowlisted field types/null flags only; no arbitrary keys/values |
| Blind dropping unsupported output | Evidence first; Google-only inert-field hook; nonempty state stays rejected |
| Ambiguous retry or budget reset | Same ledger, immutable prefix, unique case, whole-stage lock |
