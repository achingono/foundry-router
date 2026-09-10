# Phase 09 Outputs

## Mandatory Outputs

| Output | Description | Format |
| --- | --- | --- |
| Provider-aware backend config | `BackendConfig.provider` discriminator with `azure_foundry` default and `google_ai_studio` support; provider-specific validation | Source change + tests |
| Google AI Studio client support | `AllowedBackendClient` builds the Google OpenAI-compatibility URL and Google auth header for `google_ai_studio` backends; header stripped from client input | Source change + tests |
| Multi-key pool pattern | An arbitrary number of API keys represented as distinct backends in one model pool, with no A/B special case; documented config pattern | Source usage + docs + integration test |
| Rate-limit state boundary | `RateLimitStore` Protocol and in-memory implementation tracking per-key RPM/TPM/RPD with window resets, reservation, and finalization | Source change + tests |
| Rate-limit configuration | New per-backend rate-limit JSON setting with bounded validation and unknown-backend checks | Source change + tests |
| Quota-aware scoring | Rate-limit health term integrated into the explainable scoring so the highest-success key is selected; explainable `routing_decision` logs | Source change + tests |
| Reactive limit + daily reset | Google `429`/`Retry-After` drives `QUOTA_COOLDOWN`; RPD daily reset returns keys to service; no mid-stream failover | Source change + tests |
| Free-tier credit handling | A backend can opt out of dollar-credit accounting without tripping Phase 08 readiness checks; zero-cost estimation for free models | Source change + tests |
| Observability | `/admin/status` per-key remaining budget and cooldown; rate-limit metrics; secret-safe (backend ID only) | Source change + tests |
| ADR | New ADR for provider-aware, quota-based routing linked from the decisions index | Markdown |
| Updated documentation | Routing, configuration, security, observability, and traceability docs reflect verified behaviour with correct status labels | Markdown |
| Verification evidence | Test, coverage, lint, type, scan, and build results recorded | Evidence log |

## Optional Outputs
- Oldest-window-reset visibility per key in `/admin/status` if inexpensive.
- A configurable quota-health weight if tuning proves necessary (defaults conservative).

## Output Quality Checklist
- [ ] All mandatory outputs produced.
- [ ] All outputs reviewed before the gate.
- [ ] Evidence log updated with output references.
- [ ] Documentation uses `Implemented`/`Partially implemented`/`Planned`/`Design target` labels
      accurately.
- [ ] No secrets, keys, prompts, outputs, or hard-coded identifiers in source or docs.
