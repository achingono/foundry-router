# Provider evidence

**Implemented** locally, 2026-10-08. Live upstream/model compatibility remains unverified.

| Item | Reference | Notes |
| --- | --- | --- |
| Reviewed plan | `9e51334`; [contract](index.md) | Separate reviewer initially found namespace-ID and raw-path normalization gaps; both resolved and re-review cleared before runtime edits |
| Transport/config | [Unit tests](../../../tests/unit/test_compatible_provider.py) | Exact HTTPS root/port/base path, bounded body-only namespaced IDs, Bearer auth, caller-header stripping, unsafe raw paths and native/profile rejection |
| API/lifecycle | [Integration tests](../../../tests/integration/test_compatible_provider_integration.py) | 24 cases: Responses/SSE/embeddings, aliases, Google/generic failover, heterogeneous Azure/generic operations, terminal auth/5xx, only-429 failover, unsupported features, metered success/malformed/missing usage, complete/missing/truncated streaming, cancellation and cleanup |
| Regression | Immutable characterization plus Google lifecycle/integration | Existing wire fixtures unchanged; focused initial selection: 99 passed; five additional review-suggested regressions passed |
| Independent contextual review | [Implementation review](implementation-review.md) | No Critical/Major issues; both suggested broader coverage areas added |
| Full verification | Repository virtual environment | 1,669 passed, 3 platform skips, 15 Docker/Azurite deselections; overall 89.36%, compatible text module 97.37% |
| Style/types | Ruff and strict mypy | 585 files formatted, Ruff clean, 65 source files typed |
| Real local Table tests | Azurite on loopback | 14 passed; no Azure deployment claims |
| Container | `foundry-router:compatible-provider` | Docker build passed; Python 3.12.15 network-disabled app liveness and compatible response/SSE decoder smoke passed |
| Static scan | Conditional repository script absent | `scripts/quality/sonarqube-scan.sh` does not exist; contextual review still performed |
| Documentation/diff | Relative links and final diff | All 13 changed Markdown files resolved; whitespace and synthetic credential/status review passed |
| Deployment/live | None | Production remains memory/one; tests use synthetic credentials and mocked upstream |

Generic text validation is independent of Google capabilities, with 128 history items,
128 text parts per item and 256 KiB aggregate text. Shared forwarding retains historical
Google helper names, selects the actual provider adapter and preserves single-shot
conservative settlement. The fixed dialect is `max_completion_tokens` plus streaming
`stream_options.include_usage`; other dialects require explicit extensions and live evidence.
