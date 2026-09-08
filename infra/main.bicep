// Phase 07: Infrastructure as Code for Foundry Router on Azure Container Apps
// Main orchestration template for deployment of foundry-router application

metadata description = 'Azure Container Apps deployment for Foundry Router'
metadata version = '0.1.0'

// Target scope: Resource Group
targetScope = 'resourceGroup'

// Parameters for deployment customization
param location string = resourceGroup().location
param environment string = 'staging'
param appName string = 'foundry-router'

param containerImageUri string = 'foundry-router:latest'
param containerPort int = 8000
param minReplicas int = 0
param maxReplicas int = 1

// Azure Container Apps environment parameters
param logAnalyticsWorkspaceName string = '${appName}-logs-${environment}'
param containerAppEnvName string = '${appName}-env-${environment}'
param containerAppName string = '${appName}-${environment}'

// Key Vault parameters
param keyVaultName string = '${appName}-kv-${environment}'

// Tags for resource organization
param tags object = {
  environment: environment
  project: 'foundry-router'
  phase: '07'
}

// Log Analytics Workspace for diagnostics
resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2021-06-01' = {
  name: logAnalyticsWorkspaceName
  location: location
  tags: tags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

// Container Apps Environment with Log Analytics integration
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

// Key Vault for secrets storage
resource keyVault 'Microsoft.KeyVault/vaults@2023-02-01' = {
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
    accessPolicies: []
  }
}

// Container App instance for foundry-router
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
      secrets: []
      registries: []
    }
    template: {
      revisionSuffix: ''
      containers: [
        {
          name: appName
          image: containerImageUri
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

// Outputs for downstream consumption
output containerAppFqdn string = containerApp.properties.configuration.ingress.fqdn
output keyVaultUri string = keyVault.properties.vaultUri
output logAnalyticsWorkspaceId string = logAnalyticsWorkspace.id
output containerAppEnvId string = containerAppEnv.id
