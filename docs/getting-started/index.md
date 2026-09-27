# Getting Started

## Current State

The repository is **Implemented** through Phase 08, with Phase 09 **Partially implemented** (see
[Repository Status](../index.md)). It is a runnable FastAPI application that can be run locally,
built as a container image, and deployed to Azure Container Apps via the Bicep templates in
[`infra/`](../../infra/README.md).

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

## Google AI Studio Backends

Configure one backend per API key. Keys from the same Google Cloud project must share one
`quota_group`; use distinct project IDs for independent project quotas. The JSON below is
illustrative: replace every placeholder with values from your deployment secret store and the
active AI Studio rate-limit page. Do not commit real API keys.

```bash
FOUNDRY_BACKENDS_JSON='{"gemini-project-a-key-1":{"provider":"google_ai_studio","endpoint":"https://generativelanguage.googleapis.com","credential":"<secret-from-secret-store>","deployment":"gemini-2.5-flash","quota_group":"project-a","credit_metered":false},"gemini-project-b-key-1":{"provider":"google_ai_studio","endpoint":"https://generativelanguage.googleapis.com","credential":"<secret-from-secret-store>","deployment":"gemini-2.5-flash","quota_group":"project-b","credit_metered":false}}'
FOUNDRY_MODELS_JSON='{"gemini-2.5-flash":{"backends":{"gemini-project-a-key-1":1.0,"gemini-project-b-key-1":1.0}}}'
FOUNDRY_QUOTA_GROUP_RATE_LIMITS_JSON='{"project-a":{"rpm":15,"tpm":1000000,"rpd":1500},"project-b":{"rpm":15,"tpm":1000000,"rpd":1500}}'
```

The numeric limits are examples only, not router defaults. Google enforces Gemini RPM/TPM/RPD
limits per project, and the limits vary by model and tier. Quota accounting is currently
single-process; multi-replica aggregation is **Planned**.

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

