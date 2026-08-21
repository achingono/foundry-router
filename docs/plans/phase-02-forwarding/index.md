# Phase 02 API Forwarding

## Companion Documents
- [Inputs](inputs.md)
- [Activities](activities.md)
- [Outputs](outputs.md)
- [Exit Criteria](exit-criteria.md)
- [Risk Register](risk-register.md)
- [Evidence](evidence.md)

## Objective
Implement the authenticated Responses and embeddings request paths as a safe asynchronous pass-through to the configured backend pool. This phase makes the first useful proxy behavior available while preserving the existing configuration, authentication, allow-list, redaction, and correlation boundaries.

## In Scope
- Validate JSON request objects and required `model` fields.
- Reject unknown models and malformed requests without outbound traffic.
- Select the configured backend for the requested model using deterministic highest-weight selection with backend-ID tie-breaking. This is a temporary forwarding rule, not the routing policy.
- Build Azure OpenAI-compatible deployment-scoped URLs from validated endpoint, deployment, and API-version settings.
- Inject only the configured backend credential as a trusted `api-key`; never forward client credentials.
- Forward non-streaming Responses and embeddings requests and return upstream JSON/status errors.
- Pass Responses streaming bodies through as SSE without full-response buffering.
- Preserve request correlation IDs and safe response headers.
- Add mocked-backend tests for success, validation, credentials, errors, and streaming.

## Out of Scope
- Weighted routing, health states, retries, cooldowns, or failover.
- Credit estimates, reservations, reconciliation, or cost accounting.
- Chat Completions compatibility.
- Infrastructure, deployment, metrics, or real Azure integration tests.

## Backend Protocol Contract
Phase 02 targets Azure OpenAI-compatible deployment endpoints:

- `POST {endpoint}/openai/deployments/{deployment}/responses?api-version={api_version}`
- `POST {endpoint}/openai/deployments/{deployment}/embeddings?api-version={api_version}`

Each backend requires a deployment and has an optional `api_version` configuration value, defaulting to the documented Responses-capable preview version. The endpoint remains an origin/base path controlled by configuration; deployment is encoded as one path segment. Other Foundry endpoint flavors require a later explicit configuration/design change.

## Entry Criteria
- Phase 01 hardening implementation is present and its verification gates pass.
- Backend endpoints, credentials, model pools, and deployments are supplied through validated configuration.
- Phase 02 plan has received independent review.

## Exit Criteria
See [Exit Criteria](exit-criteria.md).

## Roles
- Owner: Implementation agent
- Reviewer: Independent review session
- Approver: Project maintainer
