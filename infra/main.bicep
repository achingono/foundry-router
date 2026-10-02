// Phase 10: Mode-parameterised IaC for Foundry Router on Azure Container Apps.
// Supports provisioning new or attaching to existing Container Registry and Key Vault,
// wires image pull + Key Vault secret references, and enforces interim single-replica guard.
// Minimum Bicep v0.30.0 / Azure CLI 2.60.0 (assertions evaluated by build, lint and validate).

metadata description = 'Azure Container Apps deployment for Foundry Router (Phase 10 existing-resource support)'
metadata version = '0.2.0'

targetScope = 'resourceGroup'

// --- Mode contract (Phase 10 step 1: default new keeps CI hermetic) ---
@description('Whether to provision a new Azure Container Registry or attach to an existing one.')
@allowed(['new', 'existing'])
param registryMode string = 'new'

@description('Whether to provision a new Key Vault or attach to an existing one.')
@allowed(['new', 'existing'])
param keyVaultMode string = 'new'

@description('Registry authentication mode. managedIdentity is only available for Azure Container Registry; external registries require secret mode.')
@allowed(['managedIdentity', 'secret'])
param registryAuthMode string = 'managedIdentity'

// --- Naming ---
@description('Azure region for provisioned resources.')
param location string = resourceGroup().location

@description('Deployment environment label.')
param environment string = 'staging'

@description('Application name prefix used for derived resource names.')
param appName string = 'foundry-router'

@description('Azure Container Registry name (5-50 lowercase alphanumerics, globally unique). Used in both new and existing modes.')
@minLength(5)
@maxLength(50)
param containerRegistryName string = 'foundryrouteracr'

@description('Resource group containing the registry when registryMode is existing. Defaults to the deployment resource group.')
param registryResourceGroupName string = resourceGroup().name

@description('Key Vault name (3-24 chars, globally unique). Used in both new and existing modes.')
@minLength(3)
@maxLength(24)
param keyVaultName string = 'foundry-router-kv'

@description('Resource group containing the vault when keyVaultMode is existing. Defaults to the deployment resource group.')
param keyVaultResourceGroupName string = resourceGroup().name

// --- Image coordinates (Phase 10 step 3: no free-text image reference) ---
@description('Container image repository path within the registry (no registry host, no tag).')
param imageRepository string = 'foundry-router'

@description('Container image tag.')
param imageTag string = 'latest'

@description('Explicit registry server hostname for registries outside Azure Container Registry (hostname only, no scheme, no path). Used only with secret-mode pull.')
param registryServer string = ''

@description('Registry username for secret-mode pull. Supplied via gitignored override or workflow secret.')
param registryUsername string = ''

@description('Registry password for secret-mode pull. Supply only through a gitignored *.local.json override or workflow secret.')
@secure()
param registryPassword string = ''

// --- Vault secret wiring ---
@description('Prefix for router secret names in a shared vault; defaults to an appName-derived value so rotation stays scoped.')
param secretNamePrefix string = appName

@description('Secret name (without vault URI) holding the client API keys JSON.')
param clientKeysSecretName string = 'client-api-keys'

@description('Secret name (without vault URI) holding the admin API keys JSON.')
param adminKeysSecretName string = 'admin-api-keys'

// --- App tuning ---
@description('Container port.')
param containerPort int = 8000

@description('Minimum replicas.')
@minValue(0)
@maxValue(1)
param minReplicas int = 0

@description('Maximum replicas. Interim guard: multi-replica requires the distributed state backend delivered by Phase 11.')
@minValue(0)
@maxValue(1)
param maxReplicas int = 1

@description('Log Analytics workspace name.')
param logAnalyticsWorkspaceName string = '${appName}-logs-${environment}'

@description('Container Apps environment name.')
param containerAppEnvName string = '${appName}-env-${environment}'

@description('Container App name.')
param containerAppName string = '${appName}-${environment}'

@description('Daily ingestion cap in GB, sized from the first week of measured baseline plus headroom. Conservative placeholder until measured.')
@minValue(1)
@maxValue(1000)
param dailyCapGb int = 1

@description('Table plan for ContainerAppConsoleLogs. Basic is the cost default; revert to Analytics if query/alert needs emerge (one plan switch per table per week, per-query scan charges and reduced alerting apply on Basic).')
@allowed(['Basic', 'Analytics'])
param consoleLogsPlan string = 'Basic'

@description('Resource tags.')
param tags object = {
  environment: environment
  project: 'foundry-router'
  phase: '10'
}

// --- Name-shape assertions (no @pattern in Bicep; shape rules enforced here) ---
// Vault: starts with letter, ends alphanumeric, no consecutive hyphens (length via decorators).
assert vaultStartsWithLetter = length(keyVaultName) == 0 || contains('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ', substring(keyVaultName, 0, 1))
assert vaultEndsAlphanumeric = length(keyVaultName) == 0 || contains('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', substring(keyVaultName, length(keyVaultName) - 1, 1))
assert vaultNoConsecutiveHyphens = !contains(keyVaultName, '--')
// Registry: 5-50 lowercase alphanumerics (length via decorators); must not contain hyphens or uppercase.
assert registryLowercaseAlphanumeric = containerRegistryName == toLower(containerRegistryName) && !contains(containerRegistryName, '-') && !contains(containerRegistryName, '_')
// External registry server: hostname only.
assert registryServerHostnameOnly = registryServer == '' || (!contains(registryServer, '://') && !contains(registryServer, '/'))
// Secret mode requires a credential source note (value itself never committed).
assert secretModeHasUsername = registryAuthMode != 'secret' || length(registryUsername) > 0

// --- Existing resource declarations (explicit scope for cross-RG attach) ---
resource existingRegistry 'Microsoft.ContainerRegistry/registries@2023-01-01-preview' existing = if (registryMode == 'existing') {
  name: containerRegistryName
  scope: resourceGroup(registryResourceGroupName)
}

resource existingVault 'Microsoft.KeyVault/vaults@2023-02-01' existing = if (keyVaultMode == 'existing') {
  name: keyVaultName
  scope: resourceGroup(keyVaultResourceGroupName)
}

// --- Provisioned resources ---
resource newRegistry 'Microsoft.ContainerRegistry/registries@2023-01-01-preview' = if (registryMode == 'new') {
  name: containerRegistryName
  location: location
  tags: tags
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: false
    anonymousPullEnabled: false
  }
}

resource newVault 'Microsoft.KeyVault/vaults@2023-02-01' = if (keyVaultMode == 'new') {
  name: keyVaultName
  location: location
  tags: tags
  properties: {
    tenantId: subscription().tenantId
    sku: {
      family: 'A'
      name: 'standard'
    }
    enabledForDeployment: true
    enabledForTemplateDeployment: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 90
    // Phase 10 step 7: RBAC-authorised vault so the container app managed identity can be granted access.
    enableRbacAuthorization: true
  }
}

// --- Resolve login server from the resource reference, never by concatenation ---
var newLoginServer = registryMode == 'new' ? newRegistry!.properties.loginServer : ''
var existingLoginServer = registryMode == 'existing' ? existingRegistry!.properties.loginServer : ''
var acrLoginServer = registryMode == 'new' ? newLoginServer : existingLoginServer
// External registries: server comes from the validated registryServer parameter; the two sources are never mixed.
var isExternalRegistry = registryServer != ''
var effectiveRegistryServer = isExternalRegistry ? registryServer : acrLoginServer

// Guard: managed-identity pull is only available for Azure Container Registry.
assert managedIdentityRequiresAzureRegistry = registryAuthMode != 'managedIdentity' || (!isExternalRegistry && contains(effectiveRegistryServer, '.azurecr.'))

var containerImage = '${effectiveRegistryServer}/${imageRepository}:${imageTag}'

// --- Vault URI resolved by mode ---
var newVaultUri = keyVaultMode == 'new' ? newVault!.properties.vaultUri : ''
var existingVaultUri = keyVaultMode == 'existing' ? existingVault!.properties.vaultUri : ''
var effectiveVaultUri = keyVaultMode == 'new' ? newVaultUri : existingVaultUri

var clientSecretUrl = '${effectiveVaultUri}secrets/${secretNamePrefix}-${clientKeysSecretName}'
var adminSecretUrl = '${effectiveVaultUri}secrets/${secretNamePrefix}-${adminKeysSecretName}'

// --- Log Analytics with cost guardrails ---
resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2021-06-01' = {
  name: logAnalyticsWorkspaceName
  location: location
  tags: tags
  properties: {
    sku: {
      // Pay-as-you-go held as decided non-change until a measured baseline justifies commitment tiers.
      name: 'PerGB2018'
    }
    // 30-day retention held (inside the free window).
    retentionInDays: 30
    workspaceCapping: {
      dailyQuotaGb: dailyCapGb
    }
  }
}

// Console-log table plan (Usage table stays on Analytics as the alert source).
resource consoleLogsTable 'Microsoft.OperationalInsights/workspaces/tables@2022-10-01' = {
  parent: logAnalyticsWorkspace
  name: 'ContainerAppConsoleLogs'
  properties: {
    plan: consoleLogsPlan
    // Retention stays at 30 days.
    totalRetentionInDays: 30
  }
}

// 90%-of-cap scheduled query alert over the Usage table.
resource dailyCapAlert 'Microsoft.Insights/scheduledQueryRules@2023-03-15-preview' = {
  name: '${appName}-daily-cap-90pct-${environment}'
  location: location
  tags: tags
  properties: {
    displayName: '${appName} daily ingestion at 90% of cap (${environment})'
    description: 'Fires when billable ingestion approaches the daily cap so the cause can be investigated before the cap stops ingestion.'
    severity: 2
    enabled: true
    evaluationFrequency: 'PT1H'
    windowSize: 'P1D'
    scopes: [logAnalyticsWorkspace.id]
    criteria: {
      allOf: [
        {
          query: 'Usage | where IsBillable | summarize BillableGB = sum(Quantity) / 1000 by bin(TimeGenerated, 1d) | extend CapGb = ${dailyCapGb} | where BillableGB >= 0.9 * CapGb'
          timeAggregation: 'Count'
          operator: 'GreaterThanOrEqual'
          threshold: 1
          failingPeriods: {
            numberOfEvaluationPeriods: 1
            minFailingPeriodsToAlert: 1
          }
        }
      ]
    }
  }
}

resource containerAppEnv 'Microsoft.App/managedEnvironments@2023-04-01-preview' = {
  name: containerAppEnvName
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalyticsWorkspace.properties.customerId
        sharedKey: logAnalyticsWorkspace.listKeys().primarySharedKey
      }
    }
  }
}

// --- Container App (single-revision mode explicit; single worker via image entrypoint) ---
resource containerApp 'Microsoft.App/containerApps@2023-04-01-preview' = {
  name: containerAppName
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    environmentId: containerAppEnv.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: containerPort
        transport: 'auto'
        corsPolicy: {
          allowedOrigins: ['*']
          allowedMethods: ['POST', 'GET']
          allowedHeaders: ['content-type', 'authorization', 'x-admin-key']
        }
      }
      // Registry credentials: managed-identity pull carries no credential; secret mode references a stored secret.
      secrets: concat(
        registryAuthMode == 'secret'
          ? [
              {
                name: 'registry-password'
                value: registryPassword
              }
            ]
          : [],
        [
          {
            name: '${secretNamePrefix}-client-keys'
            keyVaultUrl: clientSecretUrl
            identity: 'system'
          }
          {
            name: '${secretNamePrefix}-admin-keys'
            keyVaultUrl: adminSecretUrl
            identity: 'system'
          }
        ]
      )
      registries: registryAuthMode == 'managedIdentity'
        ? [
            {
              server: effectiveRegistryServer
              identity: 'system'
            }
          ]
        : [
            {
              server: effectiveRegistryServer
              username: registryUsername
              passwordSecretRef: 'registry-password'
            }
          ]
    }
    template: {
      revisionSuffix: ''
      containers: [
        {
          name: appName
          image: containerImage
          resources: {
            cpu: '0.25'
            memory: '0.5Gi'
          }
          ports: [
            {
              containerPort: containerPort
              protocol: 'TCP'
            }
          ]
          env: [
            {
              name: 'FOUNDRY_LOG_LEVEL'
              value: 'INFO'
            }
            {
              name: 'FOUNDRY_HTTP_MAX_CONNECTIONS'
              value: '100'
            }
            {
              name: 'FOUNDRY_HTTP_MAX_KEEPALIVE_CONNECTIONS'
              value: '20'
            }
            {
              name: 'FOUNDRY_HTTP_KEEPALIVE_EXPIRY_SECONDS'
              value: '30'
            }
            {
              name: 'FOUNDRY_GRACEFUL_SHUTDOWN_TIMEOUT_SECONDS'
              value: '30'
            }
            {
              name: 'FOUNDRY_RETRY_ATTEMPTS'
              value: '2'
            }
            {
              name: 'FOUNDRY_MIN_CREDIT_RESERVE_USD'
              value: '10.0'
            }
            {
              name: 'FOUNDRY_MIN_CREDIT_RESERVE_PERCENT'
              value: '5.0'
            }
            {
              name: 'FOUNDRY_CLIENT_API_KEYS_JSON'
              secretRef: '${secretNamePrefix}-client-keys'
            }
            {
              name: 'FOUNDRY_ADMIN_API_KEYS_JSON'
              secretRef: '${secretNamePrefix}-admin-keys'
            }
          ]
        }
      ]
      scale: {
        minReplicas: minReplicas
        maxReplicas: maxReplicas
      }
    }
  }
}

// --- Least-privilege role assignments ---
// AcrPull on the provisioned registry (same-RG inline, scoped to the registry resource).
resource acrPullNew 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (registryMode == 'new' && registryAuthMode == 'managedIdentity') {
  name: guid(resourceGroup().id, newRegistry.id, containerApp.id, '7f951dda-4ed3-4680-a7ca-43fe172d538d')
  scope: newRegistry
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
    principalId: containerApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// AcrPull on an existing registry via a module scoped to its resource group (covers cross-RG attach).
module acrPullExisting './modules/registryPullRole.bicep' = if (registryMode == 'existing' && registryAuthMode == 'managedIdentity') {
  name: 'acr-pull-${uniqueString(resourceGroup().id, containerRegistryName)}'
  scope: resourceGroup(registryResourceGroupName)
  params: {
    registryName: containerRegistryName
    principalId: containerApp.identity.principalId
  }
}

// Key Vault Secrets User on the provisioned vault (same-RG inline, scoped to the vault).
resource vaultSecretsUserNew 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (keyVaultMode == 'new') {
  name: guid(resourceGroup().id, newVault.id, containerApp.id, '4633458b-17de-408a-b874-0445c86b69e6')
  scope: newVault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')
    principalId: containerApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// Key Vault Secrets User on an existing vault via a module scoped to its resource group.
module vaultSecretsUserExisting './modules/vaultSecretsRole.bicep' = if (keyVaultMode == 'existing') {
  name: 'vault-secrets-${uniqueString(resourceGroup().id, keyVaultName)}'
  scope: resourceGroup(keyVaultResourceGroupName)
  params: {
    keyVaultName: keyVaultName
    principalId: containerApp.identity.principalId
  }
}

// --- Outputs ---
output containerAppFqdn string = containerApp.properties.configuration.ingress.fqdn
output keyVaultUri string = effectiveVaultUri
output logAnalyticsWorkspaceId string = logAnalyticsWorkspace.id
output containerAppEnvId string = containerAppEnv.id
output containerImage string = containerImage
output effectiveRegistryServer string = effectiveRegistryServer
