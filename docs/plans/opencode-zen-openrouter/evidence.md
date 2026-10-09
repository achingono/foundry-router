# Zen/OpenRouter evidence

**Implemented** locally; live upstream/model compatibility remains unverified.

| Item | Reference | Notes |
| --- | --- | --- |
| Independent plan review | [Review record](review.md) | Initial review found two Major gaps: Zen execution/accounting policy and pre-admission validation/model compatibility guarantees |
| Finding disposition | [Revised contract](index.md), [activities](activities.md), [exit criteria](exit-criteria.md) | Both findings addressed in the plan and checked by the original reviewer; cleared for implementation |
| Config and transport | `tests/unit/test_zen_openrouter_config.py`, `tests/unit/test_zen_openrouter_transport.py` | Exact HTTPS roots, operation/raw-path rejection, bounded deployment IDs, Bearer auth, caller-header stripping, Zen Responses-only URL, OpenRouter chat/embeddings URLs |
| Zen adapter | `tests/unit/test_zen_adapter.py` | Bounded stateless-text allow-list, foreign-field/bounds rejection, model-only substitution, identity success with usage, error mapping |
| Zen forwarding policy | `tests/unit/test_zen_forwarding.py` | Single-shot non-streaming/streaming, 429-only failover eligibility, terminal auth/5xx, force-charge settlement, pre-dispatch release |
| End-to-end routing/settlement | `tests/integration/test_zen_openrouter_integration.py` | Mocked upstream: alias Responses/SSE, Bearer/redaction, foreign-field and routing-extra 422s, single-dispatch 5xx, cross-group 429 failover, embeddings operation filtering |
| Full verification | Pending | Focused suites green; full tests, Ruff/mypy, Docker, SonarQube (conditional), contextual review, links and diff checks still to run |
| Documentation/diff | Partial | Config/API/security/architecture/operations/traceability updated; final link and diff review pending |
| Deployment/live | None | Production remains memory/one; tests use synthetic credentials and mocked upstream |
