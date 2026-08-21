# Phase 07 Infrastructure, Connection Tuning & Operations

## Companion Documents
- [Inputs](inputs.md)
- [Activities](activities.md)
- [Outputs](outputs.md)
- [Exit Criteria](exit-criteria.md)
- [Risk Register](risk-register.md)
- [Evidence](evidence.md)

## Objective
Establish production Infrastructure as Code (Bicep / Terraform) for Azure Container Apps (ACA) Consumption profile, configure managed identity, secrets, and Key Vault integration. Implement HTTP client connection pool and keep-alive tuning, graceful shutdown lifespan draining for active request reservations, automated CI/CD deployment pipelines, and operational smoke test suites.

## Scope

### In Scope
- Infrastructure as Code (Bicep / Terraform):
  - Azure Container Apps (ACA) Consumption profile (0.25 vCPU, 0.5 GiB, min 0, max 2+ replicas).
  - Azure Key Vault for client/admin API keys and backend credentials.
  - Managed Identity with least-privilege RBAC.
  - Optional Azure Cache for Redis for distributed state.
- HTTP Client Connection Pool & Keep-Alive Tuning:
  - Configurable `httpx.Limits` (max connections, keep-alive limits, keep-alive expiry).
  - HTTP/2 multiplexing enablement for Azure OpenAI backends.
- Graceful Lifespan Shutdown & Reservation Draining:
  - Intercept `SIGTERM` / `SIGINT` to allow active in-flight requests and streams to drain gracefully before closing sockets.
- CI/CD Deployment Pipeline & Synthetic Smoke Tests:
  - GitHub Actions automated deployment workflow.
  - End-to-end synthetic operational smoke test suite.

### Out of Scope
- Unrelated third-party cloud integrations.

## Entry Criteria
- Phases 01-06 implemented, tested, and verified.
- Docker container build and image smoke test verified.

## Exit Criteria
See [Exit Criteria](exit-criteria.md).

## Roles
- Owner: Implementation agent
- Reviewer: Independent review session
- Approver: Project maintainer
