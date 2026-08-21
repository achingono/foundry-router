# ADR-004: Backend Allow-List HTTP Client for SSRF Prevention

## Status
Accepted

## Context
The router will forward requests to Azure Foundry backends. Security requirements:
- User input must never create arbitrary outbound destinations (SSRF prevention)
- Only configured backend HTTPS origins and base paths are reachable
- Sensitive headers must not be forwarded to backends
- Must work with multiple backends across subscriptions/regions

## Decision
We will implement a **wrapper around httpx.AsyncClient** (`AllowedBackendClient`) that:
1. **Extracts configured HTTPS targets** from validated configuration at startup
2. **Validates every outbound request** against the configured scheme, host, effective port, and base path before sending
3. **Strips sensitive headers** (Authorization, api-key, Cookie, X-Forwarded-*, Forwarded)
4. **Disables redirects** and raises `SecurityError` for any request outside the configured target
5. **Exposes `allowed_hostnames` property** for testing/inspection

The allow-list is derived from `Settings.backends` (validated at startup), ensuring configuration and enforcement are consistent.

## Consequences

### Positive
- SSRF prevented by design: no code path can reach arbitrary configured-host URLs
- Configuration is single source of truth for allowed destinations
- Header stripping prevents credential leakage to backends
- Simple, auditable implementation (~100 lines)
- Testable with unit tests for allowed/blocked hosts and header stripping

### Negative
- Target validation at request time adds minimal latency
- Dynamic backend addition requires config reload (acceptable for Phase 1)
- IP-based allow-list and DNS rebinding protection are not implemented; network egress controls remain defense in depth

### Neutral
- Works with any httpx features (streaming, retries, timeouts)
- Compatible with future managed identity authentication

## Alternatives Considered
- **Network-level egress control (NSG/Firewall)**: Infrastructure-dependent, not portable, harder to test
- **Sidecar proxy (Envoy)**: Adds complexity, another moving part
- **Application Gateway / API Management**: Overkill, adds latency and cost
- **Trust httpx without validation**: Violates security requirements

## Related
- ADR-002: Configuration (allow-list derived from validated settings)
- ADR-003: Logging (redaction complements header stripping)

## References
- SSRF prevention: https://owasp.org/www-project-top-ten/2021/A10_2021-Server-Side_Request_Forgery_(SSRF)
- httpx documentation: https://www.python-httpx.org/
