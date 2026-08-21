# Phase 01: Configuration Validation, Authentication, Backend Allow-Listing, and Safe Redaction

## Companion Documents
- [Inputs](inputs.md)
- [Activities](activities.md)
- [Outputs](outputs.md)
- [Exit Criteria](exit-criteria.md)
- [Risk Register](risk-register.md)
- [Evidence](evidence.md)

## Objective
Implement the foundational configuration, authentication, and security boundary for the Foundry Router. This phase establishes the configuration schema, validates all inputs at startup, enforces client authentication on all public endpoints, restricts outbound traffic to configured backends only, and ensures no secrets or sensitive data appear in logs or responses. This is the safety foundation upon which all routing, credit, and proxy logic will be built.

## Scope

### In Scope
- Pydantic Settings configuration model with validation for all documented settings
- Environment variable and Azure Container Apps secrets loading
- Startup configuration validation with clear error messages
- Client authentication middleware (API key / Bearer token) for `/openai/v1/*` endpoints
- Administrative authentication (separate from client auth) for `/admin/status`
- Backend allow-listing: outbound HTTP client only permits configured backend endpoints
- Structured JSON logging with correlation IDs
- Log redaction for: API keys, Authorization headers, backend credentials, prompts, model outputs
- Unit tests for configuration validation, authentication, redaction, and allow-list enforcement
- Dockerfile and GitHub Actions CI workflow (lint, type-check, test, build)

### Out of Scope
- Routing logic, credit calculations, backend health, failover
- OpenAI Responses/Embeddings API proxying
- Model discovery endpoint
- Cost reconciliation with Azure Cost Management
- Metrics exposition (Prometheus / Azure Monitor)
- Infrastructure-as-code (Bicep/Terraform)
- Real Azure backend integration tests

## Entry Criteria
- Repository contains only documentation (current state)
- Python 3.12+ available in development environment
- AGENTS.md and all docs/ reviewed

## Exit Criteria
See [Exit Criteria](exit-criteria.md).

## Roles
- Owner: Implementation agent
- Reviewer: Architecture/design reviewer
- Approver: Project maintainer