# Security

## Status: Partially implemented

The proxy must not be an unrestricted public relay. Client requests require authentication, and `/admin/status` requires separate authentication. The implemented backend client accepts only configured HTTPS origins and base paths, disables redirects, and strips sensitive headers. User input must not create arbitrary outbound destinations or an SSRF path. Public listener TLS and network controls remain deployment responsibilities.

## Secret Handling

Use Azure Container Apps secrets or managed identity where practical. Never store API keys, authorization headers, credentials, prompts, or model outputs in source, Git history, Docker images, logs, or normal status responses. Log redaction must be tested rather than assumed.

## Identity and Deployment

Infrastructure should define only the RBAC and identity permissions needed for Foundry access, cost reconciliation, registry access, and deployment. GitHub Actions should prefer OIDC over long-lived credentials. Subscription IDs and resource IDs belong in deployment parameters, not source defaults.

## Required Security Tests

Tests must verify client authentication, administrative authentication, secret and authorization-header redaction, prompt/output non-logging, configured-backend-only egress, and rejection of arbitrary user-supplied endpoint URLs.
