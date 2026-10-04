// Phase 10: Mode-parameterised IaC for Foundry Router on Azure Container Apps.
// Supports provisioning new or attaching to existing Container Registry and Key Vault,
// wires image pull + Key Vault secret references, and enforces interim single-replica guard.
// Minimum Bicep v0.47.16 / Azure CLI 2.60.0 (verified typed variables/imported contracts).

metadata description = 'Azure Container Apps deployment for Foundry Router (Phase 10 existing-resource support + Phase 11 distributed state wiring)'
metadata version = '0.3.0'

targetScope = 'resourceGroup'

import { ResourceMode, RegistryAuthMode } from './types/common.bicep'
import { StateBackend, StorageTableNames } from './types/state.bicep'
import { RuntimeIdentityRef } from './types/identity.bicep'

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

// --- Distributed state backend (Phase 11) ---
@description('State backend for credit/health stores. memory is process-local; table shares state across replicas via Azure Table Storage.')
@allowed(['memory', 'table'])
param stateBackend string = 'memory'

@description('Whether to provision a new Storage account or attach to an existing one. Storage resources deploy only when stateBackend is table.')
@allowed(['new', 'existing'])
param storageMode string = 'new'

@description('Storage account name (3-24 lowercase letters and digits). Used only when stateBackend is table.')
@minLength(3)
@maxLength(24)
param storageAccountName string = 'foundryrouterst'

@description('Resource group containing the Storage account when storageMode is existing. Defaults to the deployment resource group.')
param storageResourceGroupName string = resourceGroup().name

// Keep the flat deployment parameter contract and its allowed-value validation.
// Typed internal choices are shared with the module-contract type library.
var effectiveRegistryMode ResourceMode = registryMode
var effectiveKeyVaultMode ResourceMode = keyVaultMode
var effectiveStorageMode ResourceMode = storageMode
var effectiveRegistryAuthMode RegistryAuthMode = registryAuthMode
var effectiveStateBackend StateBackend = stateBackend

@description('Prefix for the router tables in a shared Storage account (3-63 alphanumerics starting with a letter, no hyphens). Health and credit tables append fixed suffixes.')
@minLength(3)
@maxLength(50)
param tablePrefix string = replace(appName, '-', '')

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

@description('Secret name (without vault URI) holding the backends topology JSON (FOUNDRY_BACKENDS_JSON). Required: app crashes without at least one backend.')
param backendsJsonSecretName string = 'backends-json'

@description('Secret name (without vault URI) holding the models topology JSON (FOUNDRY_MODELS_JSON).')
param modelsJsonSecretName string = 'models-json'

@description('Secret name (without vault URI) holding the pricing JSON (FOUNDRY_PRICING_JSON).')
param pricingJsonSecretName string = 'pricing-json'

@description('Secret name (without vault URI) holding the backend cycle-start-day JSON (FOUNDRY_BACKEND_CYCLE_START_DAY_JSON).')
param backendCycleStartDaySecretName string = 'backend-cycle-start-day'

@description('Secret name (without vault URI) holding the backend cycle-allowance JSON (FOUNDRY_BACKEND_CYCLE_ALLOWANCE_USD_JSON).')
param backendCycleAllowanceSecretName string = 'backend-cycle-allowance'

@description('Secret name (without vault URI) holding the backend initial-remaining JSON (FOUNDRY_BACKEND_INITIAL_ESTIMATED_REMAINING_USD_JSON).')
param backendInitialRemainingSecretName string = 'backend-initial-remaining'

// --- App tuning ---
@description('Container port.')
param containerPort int = 8000

@description('Minimum replicas.')
@minValue(0)
param minReplicas int = 0

@description('Maximum replicas. Values above 1 require stateBackend table (Phase 11 distributed state); memory backends stay single-replica.')
@minValue(1)
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

@description('Console-log table plan. The current ACA Log Analytics integration creates a Classic custom-log table, which supports Analytics; Basic requires a separate DCR-based ingestion migration.')
@allowed(['Analytics'])
param consoleLogsPlan string = 'Analytics'

@description('Apply the console-log table plan after the ingestion-created table exists. Set false only for first-workspace bootstrap, then redeploy with true after confirming ingestion.')
param configureConsoleLogsPlan bool = true

@description('Email recipient for the daily ingestion cap alert.')
param alertEmailAddress string

@description('Resource tags.')
param tags object = {
  environment: environment
  project: 'foundry-router'
  phase: '11'
}

// --- Name-shape assertions (no @pattern in Bicep; shape rules enforced here) ---
// Vault: starts with letter, ends alphanumeric, no consecutive hyphens (length via decorators).
assert vaultStartsWithLetter = length(keyVaultName) == 0 || contains('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ', substring(keyVaultName, 0, 1))
assert vaultEndsAlphanumeric = length(keyVaultName) == 0 || contains('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', substring(keyVaultName, length(keyVaultName) - 1, 1))
assert vaultNoConsecutiveHyphens = !contains(keyVaultName, '--')
assert vaultCharactersValid = length(filter(range(0, length(keyVaultName)), i => !contains('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-', substring(keyVaultName, i, 1)))) == 0
// Registry: 5-50 lowercase alphanumerics (length via decorators); must not contain hyphens or uppercase.
assert registryLowercaseAlphanumeric = length(filter(range(0, length(containerRegistryName)), i => !contains('abcdefghijklmnopqrstuvwxyz0123456789', substring(containerRegistryName, i, 1)))) == 0
// External registry server: hostname only.
assert registryServerHostnameOnly = registryServer == '' || (!contains(registryServer, '://') && !contains(registryServer, '/') && !contains(registryServer, ':') && !contains(registryServer, '@') && !contains(registryServer, '?') && !contains(registryServer, '#'))
assert registryServerCharactersValid = length(filter(range(0, length(registryServer)), i => !contains('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-', substring(registryServer, i, 1)))) == 0
// Secret mode requires a credential source note (value itself never committed).
assert secretModeHasUsername = effectiveRegistryAuthMode != 'secret' || length(registryUsername) > 0

// --- Existing resource declarations (explicit scope for cross-RG attach) ---
resource existingRegistry 'Microsoft.ContainerRegistry/registries@2023-01-01-preview' existing = if (effectiveRegistryMode == 'existing' && registryServer == '') {
  name: containerRegistryName
  scope: resourceGroup(registryResourceGroupName)
}

resource existingVault 'Microsoft.KeyVault/vaults@2023-02-01' existing = if (effectiveKeyVaultMode == 'existing') {
  name: keyVaultName
  scope: resourceGroup(keyVaultResourceGroupName)
}

// --- Provisioned resources ---
resource newRegistry 'Microsoft.ContainerRegistry/registries@2023-01-01-preview' = if (effectiveRegistryMode == 'new' && registryServer == '') {
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

resource newVault 'Microsoft.KeyVault/vaults@2023-02-01' = if (effectiveKeyVaultMode == 'new') {
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
// External registries: server comes from the validated registryServer parameter; the two sources are never mixed.
var isExternalRegistry = registryServer != ''
var acrLoginServer = isExternalRegistry ? '' : (effectiveRegistryMode == 'new' ? newRegistry!.properties.loginServer : existingRegistry!.properties.loginServer)
var effectiveRegistryServer = isExternalRegistry ? registryServer : acrLoginServer

// Guard: managed-identity pull is only available for Azure Container Registry.
assert managedIdentityRequiresAzureRegistry = effectiveRegistryAuthMode != 'managedIdentity' || !isExternalRegistry

// --- Phase 11 storage validation ---
assert storageNameLowercaseAlphanumeric = length(filter(range(0, length(storageAccountName)), i => !contains('abcdefghijklmnopqrstuvwxyz0123456789', substring(storageAccountName, i, 1)))) == 0
assert tablePrefixStartsWithLetter = length(tablePrefix) == 0 || contains('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ', substring(tablePrefix, 0, 1))
assert tablePrefixAlphanumeric = length(filter(range(0, length(tablePrefix)), i => !contains('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', substring(tablePrefix, i, 1)))) == 0
// Phase 11: the Phase 10 @maxValue(1) decorator is replaced by this backend-tied assert.
assert maxReplicasAboveOneRequiresTableStateBackend = maxReplicas <= 1 || effectiveStateBackend == 'table'
assert minReplicasDoesNotExceedMaxReplicas = minReplicas <= maxReplicas

var containerImage = '${effectiveRegistryServer}/${imageRepository}:${imageTag}'

// --- Vault URI resolved by mode ---
var newVaultUri = effectiveKeyVaultMode == 'new' ? newVault!.properties.vaultUri : ''
var existingVaultUri = effectiveKeyVaultMode == 'existing' ? existingVault!.properties.vaultUri : ''
var effectiveVaultUri = effectiveKeyVaultMode == 'new' ? newVaultUri : existingVaultUri

var clientSecretUrl = '${effectiveVaultUri}secrets/${secretNamePrefix}-${clientKeysSecretName}'
var adminSecretUrl = '${effectiveVaultUri}secrets/${secretNamePrefix}-${adminKeysSecretName}'
var backendsSecretUrl = '${effectiveVaultUri}secrets/${secretNamePrefix}-${backendsJsonSecretName}'
var modelsSecretUrl = '${effectiveVaultUri}secrets/${secretNamePrefix}-${modelsJsonSecretName}'
var pricingSecretUrl = '${effectiveVaultUri}secrets/${secretNamePrefix}-${pricingJsonSecretName}'
var cycleStartDaySecretUrl = '${effectiveVaultUri}secrets/${secretNamePrefix}-${backendCycleStartDaySecretName}'
var cycleAllowanceSecretUrl = '${effectiveVaultUri}secrets/${secretNamePrefix}-${backendCycleAllowanceSecretName}'
var initialRemainingSecretUrl = '${effectiveVaultUri}secrets/${secretNamePrefix}-${backendInitialRemainingSecretName}'

// --- Log Analytics with cost guardrails ---
module observability './modules/observability.bicep' = {
  name: 'observability-${uniqueString(resourceGroup().id, logAnalyticsWorkspaceName)}'
  params: {
    config: {
      workspaceName: logAnalyticsWorkspaceName
      actionGroupName: '${appName}-cost-alerts-${environment}'
      alertName: '${appName}-daily-cap-90pct-${environment}'
      alertDisplayName: '${appName} daily ingestion at 90% of cap (${environment})'
      location: location
      tags: tags
      dailyCapGb: dailyCapGb
      alertEmailAddress: alertEmailAddress
      consoleLogsPlan: consoleLogsPlan
      configureConsoleLogsPlan: configureConsoleLogsPlan
    }
  }
}

// Keys are read only by the environment after the observability deployment.
resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2021-06-01' existing = {
  name: logAnalyticsWorkspaceName
}

resource containerAppEnv 'Microsoft.App/managedEnvironments@2023-04-01-preview' = {
  name: containerAppEnvName
  location: location
  tags: tags
  dependsOn: [observability]
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
module runtimeIdentity './modules/identity.bicep' = {
  name: 'identity-${uniqueString(resourceGroup().id, containerAppName)}'
  params: {
    config: {
      name: '${containerAppName}-runtime'
      location: location
      tags: tags
    }
  }
}

// Identity keys and inline role names must be deployment-start evaluable.
var routerIdentityResourceId = resourceId('Microsoft.ManagedIdentity/userAssignedIdentities', '${containerAppName}-runtime')
var routerIdentity RuntimeIdentityRef = {
  id: routerIdentityResourceId
  clientId: runtimeIdentity.outputs.identityRef.clientId
  principalId: runtimeIdentity.outputs.identityRef.principalId
}

resource containerApp 'Microsoft.App/containerApps@2023-04-01-preview' = {
  name: containerAppName
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${routerIdentityResourceId}': {}
    }
  }
  dependsOn: [
    acrPullNew
    acrPullExisting
    vaultSecretsUserNew
    vaultSecretsUserExisting
    storageTablesExisting
  ]
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
        effectiveRegistryAuthMode == 'secret'
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
            identity: routerIdentity.id
          }
          {
            name: '${secretNamePrefix}-admin-keys'
            keyVaultUrl: adminSecretUrl
            identity: routerIdentity.id
          }
          {
            name: '${secretNamePrefix}-backends-json'
            keyVaultUrl: backendsSecretUrl
            identity: routerIdentity.id
          }
          {
            name: '${secretNamePrefix}-models-json'
            keyVaultUrl: modelsSecretUrl
            identity: routerIdentity.id
          }
          {
            name: '${secretNamePrefix}-pricing-json'
            keyVaultUrl: pricingSecretUrl
            identity: routerIdentity.id
          }
          {
            name: '${secretNamePrefix}-backend-cycle-start-day'
            keyVaultUrl: cycleStartDaySecretUrl
            identity: routerIdentity.id
          }
          {
            name: '${secretNamePrefix}-backend-cycle-allowance'
            keyVaultUrl: cycleAllowanceSecretUrl
            identity: routerIdentity.id
          }
          {
            name: '${secretNamePrefix}-backend-initial-remaining'
            keyVaultUrl: initialRemainingSecretUrl
            identity: routerIdentity.id
          }
        ]
      )
       registries: effectiveRegistryAuthMode == 'managedIdentity'
        ? [
            {
              server: effectiveRegistryServer
              identity: routerIdentity.id
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
            {
              name: 'FOUNDRY_BACKENDS_JSON'
              secretRef: '${secretNamePrefix}-backends-json'
            }
            {
              name: 'FOUNDRY_MODELS_JSON'
              secretRef: '${secretNamePrefix}-models-json'
            }
            {
              name: 'FOUNDRY_PRICING_JSON'
              secretRef: '${secretNamePrefix}-pricing-json'
            }
            {
              name: 'FOUNDRY_BACKEND_CYCLE_START_DAY_JSON'
              secretRef: '${secretNamePrefix}-backend-cycle-start-day'
            }
            {
              name: 'FOUNDRY_BACKEND_CYCLE_ALLOWANCE_USD_JSON'
              secretRef: '${secretNamePrefix}-backend-cycle-allowance'
            }
            {
              name: 'FOUNDRY_BACKEND_INITIAL_ESTIMATED_REMAINING_USD_JSON'
              secretRef: '${secretNamePrefix}-backend-initial-remaining'
            }
            {
              name: 'FOUNDRY_STATE_BACKEND'
              value: effectiveStateBackend
            }
            {
              name: 'FOUNDRY_AZURE_CLIENT_ID'
              value: routerIdentity.clientId
            }
            {
              name: 'FOUNDRY_TABLE_ENDPOINT'
              value: tableEndpoint
            }
            {
              name: 'FOUNDRY_TABLE_HEALTH_NAME'
              value: healthTableName
            }
            {
              name: 'FOUNDRY_TABLE_CREDIT_NAME'
              value: creditTableName
            }
            {
              name: 'FOUNDRY_RATE_LIMIT_REPLICA_SHARE'
              value: string(maxReplicas)
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
resource acrPullNew 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (effectiveRegistryMode == 'new' && registryServer == '' && effectiveRegistryAuthMode == 'managedIdentity') {
  name: guid(resourceGroup().id, newRegistry.id, routerIdentityResourceId, '7f951dda-4ed3-4680-a7ca-43fe172d538d')
  scope: newRegistry
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
    principalId: routerIdentity.principalId
    principalType: 'ServicePrincipal'
  }
}

// AcrPull on an existing registry via a module scoped to its resource group (covers cross-RG attach).
module acrPullExisting './modules/registryPullRole.bicep' = if (effectiveRegistryMode == 'existing' && registryServer == '' && effectiveRegistryAuthMode == 'managedIdentity') {
  name: 'acr-pull-${uniqueString(resourceGroup().id, containerRegistryName)}'
  scope: resourceGroup(registryResourceGroupName)
  params: {
      config: {
        registryName: containerRegistryName
      }
    principalId: routerIdentity.principalId
  }
}

// Key Vault Secrets User on the provisioned vault (same-RG inline, scoped to the vault).
resource vaultSecretsUserNew 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (effectiveKeyVaultMode == 'new') {
  name: guid(resourceGroup().id, newVault.id, routerIdentityResourceId, '4633458b-17de-408a-b874-0445c86b69e6')
  scope: newVault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')
    principalId: routerIdentity.principalId
    principalType: 'ServicePrincipal'
  }
}

// Key Vault Secrets User on an existing vault via a module scoped to its resource group.
module vaultSecretsUserExisting './modules/vaultSecretsRole.bicep' = if (effectiveKeyVaultMode == 'existing') {
  name: 'vault-secrets-${uniqueString(resourceGroup().id, keyVaultName)}'
  scope: resourceGroup(keyVaultResourceGroupName)
  params: {
      config: {
        keyVaultName: keyVaultName
      }
    principalId: routerIdentity.principalId
  }
}

// --- Phase 11: Storage account, tables, and data-plane roles ---
// Deploy only when stateBackend == 'table'; memory emits no storage resources.
var healthTableName = '${tablePrefix}health'
var creditTableName = '${tablePrefix}credit'

var storageTableNames StorageTableNames = {
  storageAccountName: storageAccountName
  healthTableName: healthTableName
  creditTableName: creditTableName
}

resource existingStorage 'Microsoft.Storage/storageAccounts@2023-01-01' existing = if (effectiveStateBackend == 'table' && effectiveStorageMode == 'existing') {
  name: storageAccountName
  scope: resourceGroup(storageResourceGroupName)
}

// ARM validates disabled storage child/extension references in the root template.
// Keep the complete new-account branch inside a Table-only nested deployment.
module storageResourcesNew './modules/storageAccountResources.bicep' = if (effectiveStateBackend == 'table' && effectiveStorageMode == 'new') {
  name: 'storage-resources-${uniqueString(resourceGroup().id, storageAccountName)}'
  params: {
    config: {
      names: storageTableNames
      location: location
      tags: tags
    }
    principalId: routerIdentity.principalId
    identityResourceId: routerIdentity.id
  }
}

// Tables + table-scoped roles on an existing account via a module scoped to
// its resource group (covers cross-RG attach; the only write to an attached account).
module storageTablesExisting './modules/storageTableResources.bicep' = if (effectiveStateBackend == 'table' && effectiveStorageMode == 'existing') {
  name: 'storage-tables-${uniqueString(resourceGroup().id, storageAccountName)}'
  scope: resourceGroup(storageResourceGroupName)
  params: {
    config: {
      names: storageTableNames
    }
    principalId: routerIdentity.principalId
  }
}

// Non-secret app settings: endpoint read from primaryEndpoints, never concatenated;
// no keys, SAS tokens or connection strings are emitted anywhere.
var tableEndpointNew = (effectiveStateBackend == 'table' && effectiveStorageMode == 'new') ? storageResourcesNew!.outputs.endpoints.tableEndpoint : ''
var tableEndpointExisting = (effectiveStateBackend == 'table' && effectiveStorageMode == 'existing') ? existingStorage!.properties.primaryEndpoints.table : ''
var tableEndpoint = effectiveStateBackend == 'table' ? (effectiveStorageMode == 'new' ? tableEndpointNew : tableEndpointExisting) : ''

// --- Outputs ---
output containerAppFqdn string = containerApp.properties.configuration.ingress.fqdn
output keyVaultUri string = effectiveVaultUri
output logAnalyticsWorkspaceId string = observability.outputs.workspaceRef.workspaceId
output containerAppEnvId string = containerAppEnv.id
output containerImage string = containerImage
output effectiveRegistryServer string = effectiveRegistryServer
output tableEndpoint string = tableEndpoint
output healthTableName string = healthTableName
output creditTableName string = creditTableName
