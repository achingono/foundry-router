# Getting Started

## Current State

There is no runnable application yet. A new contributor should begin by reading the [architecture](../architecture/index.md), [routing policy](../features/routing.md), and [API contract](../api/index.md). Do not attempt to deploy the service from this repository until application and infrastructure files are added.

## Intended Local Workflow

The target local workflow is:

1. Install Python 3.12 or newer and the project dependencies once the application scaffold exists.
2. Copy `.env.example` to a local environment file. Never commit the local file or credentials.
3. Start the FastAPI service with a local configuration containing mocked Foundry backends.
4. Exercise `/health/live`, `/health/ready`, `/openai/v1/models`, Responses, embeddings, streaming, and failover behavior.
5. Run linting, type checks, unit tests, integration tests, and the container build.

## First Implementation Milestone

The first usable milestone should implement the Responses API, embeddings, model discovery, health endpoints, two configurable backends, streaming pass-through, bounded failover, and structured request accounting. Credit scheduling and reconciliation must not be replaced by an unsafe round-robin shortcut; if a capability is not ready, it must be explicit in status and documentation.

## Azure Prerequisites

The eventual deployment requires access to configured Azure AI Foundry endpoints, backend credentials or managed identities, a Container Apps environment, and appropriate RBAC. Subscription IDs, endpoints, and secrets are environment-specific and must be supplied by the operator rather than invented by an implementation agent.
