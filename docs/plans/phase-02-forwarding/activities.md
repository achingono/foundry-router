# Phase 02 Activities

## Step-By-Step Activities
1. Confirm the Phase 01 gates and inspect the existing backend client seam.
2. Add backend-specific URL construction, API-version query parameters, and trusted credential injection without weakening allow-list validation.
3. Add request validation and deterministic highest-weight pool selection with lexical tie-breaking; do not introduce health, cooldown, retry, or credit policy.
4. Implement non-streaming Responses and embeddings forwarding.
5. Implement Responses SSE pass-through with no retry or failover after output begins.
6. Add unit and integration coverage for validation, forwarding, headers, upstream errors, and streaming.
7. Update implementation-status documentation and record verification evidence.
8. Run focused tests, the full suite, lint, formatting, type checks, and applicable packaging checks.

## Review Focus
- Client and backend credentials remain separate and are never logged or echoed.
- Unknown or malformed requests make no outbound call.
- Backend URL construction cannot escape the configured origin or base path, and deployment is encoded as one path segment.
- Streaming does not buffer the complete response or retry after meaningful output.
- Upstream status, content type, and OpenAI-compatible error behavior remain explicit.
