targetScope = 'resourceGroup'

import { RouterConfig } from '../types/containers.bicep'

@description('Validated isolated test configuration; contains references, never credential values.')
param config RouterConfig
param identityResourceId string
param identityPrincipalId string
param storageResourceGroupName string
param storageAccountName string

assert isolatedOneReplica = config.minReplicas == 1 && config.maxReplicas == 1
assert isolatedTableState = config.state.backend == 'table'
assert noForwardingRetries = config.?retryAttempts == 0
assert boundedReservationLifetime = config.?reservationMaxAgeSeconds == 30
assert noModelAliases = empty(config.modelAliases)
assert separateTables = config.state.healthTableName != config.state.creditTableName

module tables '../modules/storageTableResources.bicep' = {
  name: 'table-real-inference-${uniqueString(config.name)}'
  scope: resourceGroup(storageResourceGroupName)
  params: {
    config: {
      names: {
        storageAccountName: storageAccountName
        healthTableName: config.state.healthTableName
        creditTableName: config.state.creditTableName
      }
    }
    principalId: identityPrincipalId
  }
}

module router '../modules/containers/router.bicep' = {
  name: 'router-real-inference-${uniqueString(config.name)}'
  params: {
    config: config
    identityResourceId: identityResourceId
  }
  dependsOn: [tables]
}

output fqdn string = router.outputs.routerRef.fqdn
