// Opt-in public typed adapter; main.bicep remains the flat orchestration boundary.
targetScope = 'resourceGroup'

import { DeploymentRegistry, VaultLifecycle, DeploymentState } from './types/deployment.bicep'

@description('ACR lifecycle/authentication or an external registry using secret authentication.')
param registry DeploymentRegistry

@description('Provision a vault in this resource group or attach to an existing vault.')
param vault VaultLifecycle

@description('Memory state or Azure Table state with a new/existing account.')
param state DeploymentState

@description('Azure region for provisioned resources.')
param location string = resourceGroup().location

@description('Deployment environment label.')
param environment string = 'staging'

@description('Application name prefix used for derived resource names.')
param appName string = 'foundry-router'

@description('Table-name prefix, including memory-mode output names. Table state may override this value.')
@minLength(3)
@maxLength(50)
param tablePrefix string = replace(appName, '-', '')

@description('Container image repository path within the registry (no registry host, no tag).')
param imageRepository string = 'foundry-router'

@description('Container image tag.')
param imageTag string = 'latest'

@description('Registry password for secret-mode pull. Supply through a gitignored override or workflow secret.')
@secure()
param registryPassword string = ''

@description('Prefix for router secret names in a shared vault.')
param secretNamePrefix string = appName

@description('Secret name holding the client API keys JSON.')
param clientKeysSecretName string = 'client-api-keys'

@description('Secret name holding the admin API keys JSON.')
param adminKeysSecretName string = 'admin-api-keys'

@description('Secret name holding the backends topology JSON; at least one backend is required.')
param backendsJsonSecretName string = 'backends-json'

@description('Secret name holding the models topology JSON.')
param modelsJsonSecretName string = 'models-json'

@description('Secret name holding the pricing JSON.')
param pricingJsonSecretName string = 'pricing-json'

@description('Secret name holding the backend cycle-start-day JSON.')
param backendCycleStartDaySecretName string = 'backend-cycle-start-day'

@description('Secret name holding the backend cycle-allowance JSON.')
param backendCycleAllowanceSecretName string = 'backend-cycle-allowance'

@description('Secret name holding the backend initial-remaining JSON.')
param backendInitialRemainingSecretName string = 'backend-initial-remaining'

@description('Container port.')
param containerPort int = 8000

@description('Minimum replicas.')
@minValue(0)
param minReplicas int = 0

@description('Maximum replicas. Values above 1 require Table state; production remains memory-backed with one replica until cut-over gates pass.')
@minValue(1)
param maxReplicas int = 1

@description('Log Analytics workspace name.')
param logAnalyticsWorkspaceName string = '${appName}-logs-${environment}'

@description('Container Apps environment name.')
param containerAppEnvName string = '${appName}-env-${environment}'

@description('Container App name.')
param containerAppName string = '${appName}-${environment}'

@description('Daily ingestion cap in GB; conservative placeholder until measured.')
@minValue(1)
@maxValue(1000)
param dailyCapGb int = 1

@description('Classic console-log table plan; Basic requires a separate DCR-based ingestion migration.')
@allowed(['Analytics'])
param consoleLogsPlan string = 'Analytics'

@description('Apply the console-log plan after ingestion creates the table; set false for first-workspace bootstrap.')
param configureConsoleLogsPlan bool = true

@description('Email recipient for the daily ingestion cap alert.')
param alertEmailAddress string

@description('Resource tags.')
param tags object = {
  environment: environment
  project: 'foundry-router'
  phase: '11'
}

// Inactive names still pass main.bicep's unconditional name validation.
// External server and memory backend guards prevent placeholder resources from deploying.
module deployment './main.bicep' = {
  name: 'typed-${uniqueString(resourceGroup().id, containerAppName)}'
  params: {
    registryMode: registry.kind == 'acr' ? registry.acr.mode : 'new'
    keyVaultMode: vault.mode
    registryAuthMode: registry.kind == 'acr' ? registry.auth.mode : 'secret'
    location: location
    environment: environment
    appName: appName
    containerRegistryName: registry.kind == 'acr' ? registry.acr.name : 'unusedacr'
    registryResourceGroupName: registry.kind == 'acr' ? (registry.acr.mode == 'existing' ? registry.acr.resourceGroup : resourceGroup().name) : resourceGroup().name
    registrySubscriptionId: registry.kind == 'acr' && registry.acr.mode == 'existing' ? (registry.acr.?subscriptionId ?? subscription().subscriptionId) : subscription().subscriptionId
    keyVaultName: vault.name
    keyVaultResourceGroupName: vault.mode == 'existing' ? vault.resourceGroup : resourceGroup().name
    stateBackend: state.backend
    storageMode: state.backend == 'table' ? state.account.mode : 'new'
    storageAccountName: state.backend == 'table' ? state.account.name : 'unusedstorage'
    storageResourceGroupName: state.backend == 'table' ? (state.account.mode == 'existing' ? state.account.resourceGroup : resourceGroup().name) : resourceGroup().name
    tablePrefix: state.backend == 'table' ? (state.?tablePrefix ?? tablePrefix) : tablePrefix
    imageRepository: imageRepository
    imageTag: imageTag
    registryServer: registry.kind == 'external' ? registry.server : ''
    registryUsername: registry.kind == 'external' ? registry.username : (registry.auth.mode == 'secret' ? registry.auth.username : '')
    registryPassword: registryPassword
    secretNamePrefix: secretNamePrefix
    clientKeysSecretName: clientKeysSecretName
    adminKeysSecretName: adminKeysSecretName
    backendsJsonSecretName: backendsJsonSecretName
    modelsJsonSecretName: modelsJsonSecretName
    pricingJsonSecretName: pricingJsonSecretName
    backendCycleStartDaySecretName: backendCycleStartDaySecretName
    backendCycleAllowanceSecretName: backendCycleAllowanceSecretName
    backendInitialRemainingSecretName: backendInitialRemainingSecretName
    containerPort: containerPort
    minReplicas: minReplicas
    maxReplicas: maxReplicas
    logAnalyticsWorkspaceName: logAnalyticsWorkspaceName
    containerAppEnvName: containerAppEnvName
    containerAppName: containerAppName
    dailyCapGb: dailyCapGb
    consoleLogsPlan: consoleLogsPlan
    configureConsoleLogsPlan: configureConsoleLogsPlan
    alertEmailAddress: alertEmailAddress
    tags: tags
  }
}

output containerAppFqdn string = deployment.outputs.containerAppFqdn
output keyVaultUri string = deployment.outputs.keyVaultUri
output logAnalyticsWorkspaceId string = deployment.outputs.logAnalyticsWorkspaceId
output containerAppEnvId string = deployment.outputs.containerAppEnvId
output containerImage string = deployment.outputs.containerImage
output effectiveRegistryServer string = deployment.outputs.effectiveRegistryServer
output tableEndpoint string = deployment.outputs.tableEndpoint
output healthTableName string = deployment.outputs.healthTableName
output creditTableName string = deployment.outputs.creditTableName
