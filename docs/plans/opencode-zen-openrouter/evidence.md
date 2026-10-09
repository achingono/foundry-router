# Zen/OpenRouter evidence

**Implemented** locally, 2026-10-09. Live upstream/model compatibility remains unverified.

| Item | Reference | Notes |
| --- | --- | --- |
| Independent plan review | [Review record](review.md) | Initial review found two Major gaps: Zen execution/accounting policy and pre-admission validation/model compatibility guarantees |
| Finding disposition | [Revised contract](index.md), [activities](activities.md), [exit criteria](exit-criteria.md) | Both findings addressed in the plan and checked by the original reviewer; cleared for implementation |
| Config and transport | `tests/unit/test_zen_openrouter_config.py`, `tests/unit/test_zen_openrouter_transport.py` | Exact HTTPS roots, operation/raw-path rejection, bounded deployment IDs, Bearer auth, caller-header stripping, Zen Responses-only URL, OpenRouter chat/embeddings URLs |
| Zen adapter | `tests/unit/test_zen_adapter.py` | Bounded stateless-text allow-list, foreign-field/bounds rejection, model-only substitution, identity success with usage, error mapping |
| Zen forwarding policy | `tests/unit/test_zen_forwarding.py` | Single-shot non-streaming/streaming, 429-only failover eligibility, terminal auth/5xx, force-charge settlement, pre-dispatch release |
| End-to-end routing/settlement | `tests/integration/test_zen_openrouter_integration.py` | Mocked upstream: alias Responses/SSE, Bearer/redaction, foreign-field and routing-extra 422s, single-dispatch 5xx, cross-group 429 failover, embeddings operation filtering |
| Full verification | Repository virtual environment | 2,203 passed, 3 skipped, 19 deselected (`not docker and not azurite`); total coverage 89.81% (gate 80%), `zen.py` 95.24% |
| Style/types | Ruff and strict mypy | `ruff check src tests` clean; `ruff format` applied; mypy strict clean on touched source files |
| Container | `foundry-router:zen-openrouter` | Docker build passed; network-disabled liveness, Zen/OpenRouter model listing, and full readiness (`ready: true` with complete credit config) verified |
| Static scan | Conditional repository script absent | `scripts/quality/sonarqube-scan.sh` does not exist; contextual review still performed |
| Contextual review | [Implementation review](implementation-review.md) | No Critical/Major issues; one naming-debt Suggestion recorded |
| Documentation/diff | Relative links and final diff | All touched Markdown links resolve; no trailing whitespace; synthetic-only credentials; no unsupported live claims |
| Deployment/live | None | Production remains memory/one; tests use synthetic credentials and mocked upstream |

Google-named shared forwarding helpers (`_enter_google_stream`,
`_handle_google_error_status`) are provider-parameterized and safe for Zen reuse;
pre-output failover stays Google-only. Zen streaming shares the bounded SSE usage
inspector; Zen success settles through the standard finalizer, which charges the
reserved estimate when usage is missing rather than zero.
