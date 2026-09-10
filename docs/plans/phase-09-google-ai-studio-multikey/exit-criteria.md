# Phase 09 Exit Criteria

## Gate Checklist
- [ ] A backend can be configured with `provider: "google_ai_studio"`; the backend client builds
      the Google OpenAI-compatibility URL and sets the Google auth header from the backend
      credential; Azure backends are unchanged.
- [ ] The Google OpenAI-compatibility base URL and auth header name are confirmed against current
      Google documentation, recorded in the ADR, and driven by configuration rather than hard-coded
      guesses.
- [ ] An arbitrary number of API keys can back one model as distinct backends with no A/B or
      two-key special case; an integration test proves cross-key routing under scoring rules.
- [ ] Per-key RPM, TPM, and RPD are tracked with correct minute- and day-window rollovers;
      reservation and finalization reconcile estimated vs actual token usage; unit tests cover
      rollover, reconciliation, exhaustion, and reset.
- [ ] Selection is quota-aware: among otherwise-equal keys the one with the most remaining headroom
      is chosen, a key near its limit is deprioritised or skipped, and the decision is deterministic
      and explainable via `routing_decision` logs. It is not round-robin.
- [ ] A rate-limit reservation uses the server-owned request key (never a client value) and is
      released on failover and on request abandonment.
- [ ] Google `429`/`Retry-After` drives `QUOTA_COOLDOWN` through the existing health path; RPD daily
      reset returns a key to service; no failover occurs after meaningful streaming output begins.
- [ ] Free-tier backends are routable without dollar-credit configuration and do not trip the Phase
      08 readiness completeness checks; metered Azure backends still fail readiness when credit
      config is missing; the chosen approach is recorded.
- [ ] No API key, credential, prompt, or model output appears in logs, errors, `/admin/status`,
      metric labels, or docs; the Google auth header is stripped from client-supplied headers.
- [ ] `/admin/status` exposes per-key remaining budget and cooldown by backend ID; rate-limit
      metrics are present and consistent with the existing metrics approach.
- [ ] Streaming/SSE event boundaries and the no-retry-after-output rule remain intact.
- [ ] Full suite passes via `.venv/bin/python -m pytest -m "not docker" -q`; coverage for
      implemented code is >= 80%.
- [ ] Ruff, formatter, and Mypy pass; SonarQube scan and deep-review prompt (where present) have no
      unresolved `Blocker`/`Critical`/`Major` findings (note N/A if absent).
- [ ] Docker build succeeds where the CLI is available (note N/A otherwise).
- [ ] Routing, configuration, security, observability, and traceability docs plus the new ADR are
      updated with verified behaviour only; relative links validated.
- [ ] Final diff reviewed for unsupported present-tense claims, secrets, or hard-coded identifiers.

## Approval Table

| Role | Name | Status | Notes |
| --- | --- | --- | --- |
| Owner | | Pending | |
| Reviewer | | Pending | |
| Approver | | Pending | |
