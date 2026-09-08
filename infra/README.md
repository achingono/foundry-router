# Foundry Router Infrastructure as Code (Phase 07)

## Overview

This directory contains Azure Bicep Infrastructure as Code (IaC) templates for deploying Foundry Router on Azure Container Apps (ACA).

## Structure

- `main.bicep`: Main orchestration template defining all resources
- `parameters.staging.json`: Parameter overrides for staging environment
- `parameters.prod.json`: Parameter overrides for production environment
- `README.md`: This file

## Prerequisites

1. Azure CLI with Bicep support (`az bicep install`)
2. An Azure subscription and Resource Group
3. Container registry with foundry-router image published

## Deployment

### Validate Template

```bash
az bicep build --file infra/main.bicep
az deployment group validate \
  --resource-group $RESOURCE_GROUP \
  --template-file infra/main.bicep \
  --parameters infra/parameters.staging.json
```

### Deploy to Staging

```bash
az deployment group create \
  --name foundry-router-staging-$(date +%s) \
  --resource-group $RESOURCE_GROUP \
  --template-file infra/main.bicep \
  --parameters infra/parameters.staging.json
```

### Deploy to Production

```bash
az deployment group create \
  --name foundry-router-prod-$(date +%s) \
  --resource-group $RESOURCE_GROUP \
  --template-file infra/main.bicep \
  --parameters infra/parameters.prod.json
```

## Resources Created

- **Log Analytics Workspace**: Centralized logging and diagnostics (30-day retention)
- **Container Apps Environment**: Managed infrastructure for container apps
- **Container App**: Foundry Router application instance
  - Consumption pricing tier (0.25 vCPU, 0.5 GiB minimum)
  - Configurable min/max replicas per environment
  - HTTP/HTTPS ingress with CORS support
- **Key Vault**: Secrets storage for API keys and credentials

## Configuration

### Environment Variables

The container app is configured with the following environment variables:

| Variable | Staging | Production |
|----------|---------|------------|
| `FOUNDRY_LOG_LEVEL` | INFO | INFO |
| `FOUNDRY_HTTP_MAX_CONNECTIONS` | 100 | 100 |
| `FOUNDRY_HTTP_MAX_KEEPALIVE_CONNECTIONS` | 20 | 20 |
| `FOUNDRY_HTTP_KEEPALIVE_EXPIRY_SECONDS` | 30 | 30 |
| `FOUNDRY_GRACEFUL_SHUTDOWN_TIMEOUT_SECONDS` | 30 | 30 |
| `FOUNDRY_RETRY_ATTEMPTS` | 2 | 2 |
| `FOUNDRY_MIN_CREDIT_RESERVE_USD` | 10.0 | 10.0 |
| `FOUNDRY_MIN_CREDIT_RESERVE_PERCENT` | 5.0 | 5.0 |

### Scaling

- **Staging**: 0 min replicas (scale to zero), max 1 replica
- **Production**: 1 min replica (always active), max 2 replicas

Adjust `minReplicas` and `maxReplicas` in parameter files as needed.

## Secrets Management

API keys and credentials should be:
1. Stored in Azure Key Vault
2. Referenced via Key Vault secret references in environment variables
3. Never committed to version control

## Monitoring & Diagnostics

Logs are automatically collected in Log Analytics Workspace:
- Application logs via STDOUT/STDERR
- Container app metrics and events
- HTTP request traces

Query logs:
```kusto
ContainerAppConsoleLogs
| where ContainerAppName == 'foundry-router-staging'
| order by TimeGenerated desc
| limit 100
```

## Security Considerations

- Container App uses system-assigned managed identity (Phase 08: RBAC to Key Vault)
- Ingress is HTTPS-only (automatic with Azure Container Apps)
- CORS policy restricts to configured origins only
- Secrets are never logged or exposed in container environment variables
- Soft delete enabled on Key Vault (90-day retention)

## Health Checks

After deployment, verify the application is running:

```bash
# Get FQDN
FQDN=$(az deployment group show \
  --name foundry-router-staging-* \
  --resource-group $RESOURCE_GROUP \
  --query 'properties.outputs.containerAppFqdn.value' -o tsv)

# Test liveness
curl https://$FQDN/health/live

# Test readiness
curl https://$FQDN/health/ready
```

## Cleanup

To remove all resources:

```bash
az deployment group delete \
  --name foundry-router-staging-* \
  --resource-group $RESOURCE_GROUP
```

Note: Key Vault is soft-deleted and can be recovered within 90 days.

## Next Steps

- Phase 07-CI/CD: Add GitHub Actions deployment workflow
- Phase 07-Operations: Add operational smoke test suite
- Phase 08: Configure managed identity RBAC for Key Vault access
