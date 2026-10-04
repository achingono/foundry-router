targetScope = 'resourceGroup'

import { NewRegistryConfig, RegistryRef } from '../types/resources.bicep'

param config NewRegistryConfig
param identityResourceId string
param principalId string

resource registry 'Microsoft.ContainerRegistry/registries@2023-01-01-preview' = {
  name: config.name
  location: config.location
  tags: config.tags
  sku: { name: 'Basic' }
  properties: {
    adminUserEnabled: false
    anonymousPullEnabled: false
  }
}

resource acrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (config.grantPull) {
  // Exact original new-resource GUID formula; differs from existing-resource grants.
  name: guid(resourceGroup().id, registry.id, identityResourceId, '7f951dda-4ed3-4680-a7ca-43fe172d538d')
  scope: registry
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}

output registryRef RegistryRef = {
  id: registry.id
  loginServer: registry.properties.loginServer
}
