# Development Workflow

## Status: Planned

Implement incrementally from the boundaries in [architecture](../architecture/index.md). Prefer a small asynchronous Python service and avoid heavyweight infrastructure. Keep behavior feature-local, document Azure-specific assumptions, and preserve the client model name and streaming semantics.

## Local Development

Use mocked Foundry backends for normal development and integration tests. Real Azure credentials may be used only by an explicit, opt-in end-to-end test and must never run automatically in pull requests.

## Quality Gates

Every implementation change should run formatting/linting, type checks where configured, unit tests, integration tests, and a Docker build where relevant. Maintain at least 80% coverage for implemented code. Review logs for secrets and inspect the final diff before merging.

## Pull Requests and Deployment

Pull requests should install dependencies, lint, type-check, test, and build the image. Main-branch deployment should build and push to ACR, deploy IaC and the Container App using approved authentication, and run a smoke test. Production credentials should use GitHub OIDC where possible.
