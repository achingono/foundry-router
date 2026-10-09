# Provider exit criteria

- [x] Independent plan review completed and findings addressed before runtime changes.
- [ ] Exact API root and Bearer auth verified; no arbitrary target/auth forwarding.
- [ ] Independent bounded text history; unsupported features rejected before admission.
- [ ] Responses/embeddings and SSE use the actual provider adapter.
- [ ] Mixed pools/aliases and quota/credit separation preserved.
- [ ] No post-output retries; ambiguous dispatch/cancellation settlement verified.
- [ ] Existing Google oracle and suites unchanged and passing.
- [ ] Full tests/coverage ≥80%, Ruff/mypy, Docker, deep review, links and diff checks pass.
- [ ] Canonical documentation/traceability updated and transition committed.

Live upstream support is not established by the local implementation gate.
