targetScope = 'resourceGroup'

import { RouterConfig, RouterRef } from '../../types/containers.bicep'

param config RouterConfig

@description('Deployment-start evaluable runtime identity resource ID.')
param identityResourceId string

@description('Registry pull password; kept outside ordinary configuration objects.')
@secure()
param registryPassword string = ''

assert minReplicasDoesNotExceedMaxReplicas = config.minReplicas <= config.maxReplicas
assert maxReplicasAboveOneRequiresTableStateBackend = config.maxReplicas <= 1 || config.state.backend == 'table'
assert managedIdentityRequiresAzureRegistry = config.registry.authMode != 'managedIdentity' || !config.registry.isExternalRegistry
assert secretModeHasUsername = config.registry.authMode != 'secret' || length(config.registry.username) > 0

resource router 'Microsoft.App/containerApps@2023-04-01-preview' = {
  name: config.name
  location: config.location
  tags: config.tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identityResourceId}': {}
    }
  }
  properties: {
    environmentId: config.environmentId
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: config.containerPort
        transport: 'auto'
        corsPolicy: {
          allowedOrigins: ['*']
          allowedMethods: ['POST', 'GET']
          allowedHeaders: ['content-type', 'authorization', 'x-admin-key']
        }
      }
      secrets: concat(
        config.registry.authMode == 'secret'
          ? [{ name: 'registry-password', value: registryPassword }]
          : [],
        [
          {
            name: '${config.secretNamePrefix}-client-keys'
            keyVaultUrl: config.secretUrls.clientKeys
            identity: identityResourceId
          }
          {
            name: '${config.secretNamePrefix}-admin-keys'
            keyVaultUrl: config.secretUrls.adminKeys
            identity: identityResourceId
          }
          {
            name: '${config.secretNamePrefix}-backends-json'
            keyVaultUrl: config.secretUrls.backends
            identity: identityResourceId
          }
          {
            name: '${config.secretNamePrefix}-models-json'
            keyVaultUrl: config.secretUrls.models
            identity: identityResourceId
          }
          {
            name: '${config.secretNamePrefix}-pricing-json'
            keyVaultUrl: config.secretUrls.pricing
            identity: identityResourceId
          }
          {
            name: '${config.secretNamePrefix}-backend-cycle-start-day'
            keyVaultUrl: config.secretUrls.cycleStartDay
            identity: identityResourceId
          }
          {
            name: '${config.secretNamePrefix}-backend-cycle-allowance'
            keyVaultUrl: config.secretUrls.cycleAllowance
            identity: identityResourceId
          }
          {
            name: '${config.secretNamePrefix}-backend-initial-remaining'
            keyVaultUrl: config.secretUrls.initialRemaining
            identity: identityResourceId
          }
        ]
      )
      registries: config.registry.authMode == 'managedIdentity'
        ? [{ server: config.registry.server, identity: identityResourceId }]
        : [{ server: config.registry.server, username: config.registry.username, passwordSecretRef: 'registry-password' }]
    }
    template: {
      revisionSuffix: ''
      containers: [
        {
          name: config.containerName
          image: config.image
          resources: {
            cpu: '0.25'
            memory: '0.5Gi'
          }
          env: [
            { name: 'FOUNDRY_LOG_LEVEL', value: 'INFO' }
            { name: 'FOUNDRY_HTTP_MAX_CONNECTIONS', value: '100' }
            { name: 'FOUNDRY_HTTP_MAX_KEEPALIVE_CONNECTIONS', value: '20' }
            { name: 'FOUNDRY_HTTP_KEEPALIVE_EXPIRY_SECONDS', value: '30' }
            { name: 'FOUNDRY_GRACEFUL_SHUTDOWN_TIMEOUT_SECONDS', value: '30' }
            { name: 'FOUNDRY_RETRY_ATTEMPTS', value: '2' }
            { name: 'FOUNDRY_MIN_CREDIT_RESERVE_USD', value: '10.0' }
            { name: 'FOUNDRY_MIN_CREDIT_RESERVE_PERCENT', value: '5.0' }
            { name: 'FOUNDRY_CLIENT_API_KEYS_JSON', secretRef: '${config.secretNamePrefix}-client-keys' }
            { name: 'FOUNDRY_ADMIN_API_KEYS_JSON', secretRef: '${config.secretNamePrefix}-admin-keys' }
            { name: 'FOUNDRY_BACKENDS_JSON', secretRef: '${config.secretNamePrefix}-backends-json' }
            { name: 'FOUNDRY_MODELS_JSON', secretRef: '${config.secretNamePrefix}-models-json' }
            { name: 'FOUNDRY_PRICING_JSON', secretRef: '${config.secretNamePrefix}-pricing-json' }
            { name: 'FOUNDRY_BACKEND_CYCLE_START_DAY_JSON', secretRef: '${config.secretNamePrefix}-backend-cycle-start-day' }
            { name: 'FOUNDRY_BACKEND_CYCLE_ALLOWANCE_USD_JSON', secretRef: '${config.secretNamePrefix}-backend-cycle-allowance' }
            { name: 'FOUNDRY_BACKEND_INITIAL_ESTIMATED_REMAINING_USD_JSON', secretRef: '${config.secretNamePrefix}-backend-initial-remaining' }
            { name: 'FOUNDRY_STATE_BACKEND', value: config.state.backend }
            { name: 'FOUNDRY_AZURE_CLIENT_ID', value: config.clientId }
            { name: 'FOUNDRY_TABLE_ENDPOINT', value: config.state.endpoint }
            { name: 'FOUNDRY_TABLE_HEALTH_NAME', value: config.state.healthTableName }
            { name: 'FOUNDRY_TABLE_CREDIT_NAME', value: config.state.creditTableName }
            { name: 'FOUNDRY_RATE_LIMIT_REPLICA_SHARE', value: string(config.maxReplicas) }
          ]
        }
      ]
      scale: {
        minReplicas: config.minReplicas
        maxReplicas: config.maxReplicas
      }
    }
  }
}

output routerRef RouterRef = {
  id: router.id
  fqdn: router.properties.configuration.ingress.fqdn
}
