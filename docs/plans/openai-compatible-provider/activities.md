# Provider activities

1. Obtain independent model/session plan review and resolve findings before runtime changes.
2. Validate provider, exact HTTPS API root, declared operations and physical model. Test
   native/Google-profile rejection and operation/path/query confusion. Validate unsafe raw
   paths before URL normalization; permit bounded body-only namespaced generic model IDs
   without weakening Azure/Google path-segment validation.
3. Implement independent bounded text context/history hooks. Define node/byte/depth limits
   comparable to existing intake without Google profile/media/schema helper imports.
4. Implement exact-root URL construction, model substitution and Bearer injection. Test
   caller auth stripping, exact origin/port/path confinement and disabled redirects. Exercise
   namespace/model identifiers in both Responses and embeddings with the documented fixed
   `max_completion_tokens`/`stream_options.include_usage` dialect.
5. Share necessary translated forwarding using actual provider selection. Preserve existing
   Google private helpers where callers/tests depend on them; distinguish translated transport
   from Google native/media branches. Verify failure/usage/failover semantics.
6. Add real ASGI tests with mocked upstream: normal/streaming Responses, embeddings,
   mixed pools/aliases, 429/auth/5xx, malformed envelopes, post-output failure, cancellation,
   missing usage, cleanup and redaction. Run the unchanged Google oracle.
7. Update configuration, API, security, architecture, operations and requirements traceability.
8. Run focused/full tests with ≥80% coverage, Ruff/mypy, Docker build/smoke, conditional
   SonarQube, contextual review, links and final diff. Commit the phase transition.

Review focus: base-path/auth ownership, independent bounded validation, no Azure fallthrough,
conservative billable failures and no post-output retry.
