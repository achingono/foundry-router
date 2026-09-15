# Getting Started

## Current State

The repository is **Implemented** through Phase 08 (see [Repository Status](../index.md)). It is a
runnable FastAPI application that can be run locally, built as a container image, and deployed to
Azure Container Apps via the Bicep templates in [`infra/`](../../infra/README.md).

## Local Run

1. Install Python 3.12 or newer.
2. Create and activate a virtual environment, then install the package with development
   dependencies:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -e ".[dev]"
   ```

3. Copy [`.env.example`](../../.env.example) to `.env` and replace the placeholder backend
   endpoints, credentials, and API keys with real or mock values. Never commit `.env` or real
   credentials.
4. Start the service:

   ```bash
   uvicorn foundry_router.main:app --host 0.0.0.0 --port 8000 --reload
   ```

5. Exercise the API. Client endpoints require either an `api-key` header or an
   `Authorization: Bearer <key>` header matching `FOUNDRY_CLIENT_API_KEYS_JSON`; `/admin/status`
   and `/metrics` require an `x-admin-key` header or bearer token matching
   `FOUNDRY_ADMIN_API_KEYS_JSON`:

   ```bash
   curl http://localhost:8000/health/live
   curl http://localhost:8000/health/ready
   curl -H "api-key: replace-client-key" http://localhost:8000/openai/v1/models
   curl -H "x-admin-key: replace-admin-key" http://localhost:8000/admin/status
   ```

See [Configuration](../configuration/index.md) and [Security](../configuration/security.md) for
the full set of environment variables and authentication behavior.

## Verification

Before opening a change, run the same checks CI enforces:

```bash
ruff check .
ruff format --check .
mypy src/
pytest tests/unit/ tests/integration/ -v --cov=src/foundry_router --cov-report=term-missing --cov-fail-under=80
```

## Docker Build

```bash
docker build -t foundry-router:local .
docker run --rm -p 8000:8000 --env-file .env foundry-router:local
curl http://localhost:8000/health/live
```

The image runs as a non-root user and includes a `HEALTHCHECK` against `/health/live`.

## Azure Deployment (Bicep)

Deployment targets Azure Container Apps using the templates in [`infra/`](../../infra/README.md).
Prerequisites: Azure CLI with Bicep support, an Azure subscription and resource group, and a
container registry with the `foundry-router` image published.

```bash
az bicep build --file infra/main.bicep
az deployment group validate \
  --resource-group $RESOURCE_GROUP \
  --template-file infra/main.bicep \
  --parameters infra/parameters.staging.json

az deployment group create \
  --name foundry-router-staging-$(date +%s) \
  --resource-group $RESOURCE_GROUP \
  --template-file infra/main.bicep \
  --parameters infra/parameters.staging.json
```

Use `infra/parameters.prod.json` for production. `.github/workflows/deploy.yml` automates this as
a staged pipeline (build image, validate Bicep, deploy staging with smoke tests, manual production
approval) using `scripts/operations/smoke-test.sh` for post-deploy validation. Subscription IDs,
endpoints, and secrets are environment-specific and must be supplied by the operator, never
hard-coded.

## Azure Prerequisites

Deployment requires access to configured Azure AI Foundry endpoints, backend credentials or
managed identities, a Container Apps environment, and appropriate RBAC (see
[Security](../configuration/security.md)).

