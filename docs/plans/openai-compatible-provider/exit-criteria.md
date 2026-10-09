# Provider exit criteria

- [x] Independent plan review completed and findings addressed before runtime changes.
- [x] Exact API root and Bearer auth verified; no arbitrary target/auth forwarding.
- [x] Independent bounded text history; unsupported features rejected before admission.
- [x] Responses/embeddings and SSE use the actual provider adapter.
- [x] Mixed pools/aliases and quota/credit separation preserved.
- [x] No post-output retries; ambiguous dispatch/cancellation settlement verified.
- [x] Existing Google oracle and suites unchanged and passing.
- [x] Full tests/coverage ≥80%, Ruff/mypy, Docker, deep review, links and diff checks pass.
- [x] Canonical documentation/traceability updated and included in the phase-transition commit.

Live upstream support is not established by the local implementation gate.
