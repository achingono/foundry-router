// Scoped registry pull role assignment for an existing registry in another resource group.
targetScope = 'resourceGroup'

import { RegistryPullConfig } from '../types/access.bicep'

@description('Name of the existing container registry.')
param config RegistryPullConfig

@description('Principal ID of the pre-created container app runtime identity.')
param principalId string

@description('Deterministic suffix for the role assignment name.')
param assignmentSuffix string = uniqueString(resourceGroup().id, config.registryName, principalId)

// Azure Container Registry Pull built-in role (tenant-independent GUID).
var acrPullRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '7f951dda-4ed3-4680-a7ca-43fe172d538d'
)

resource existingRegistry 'Microsoft.ContainerRegistry/registries@2023-01-01-preview' existing = {
  name: config.registryName
}

resource acrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, existingRegistry.id, principalId, acrPullRoleId, assignmentSuffix)
  scope: existingRegistry
  properties: {
    roleDefinitionId: acrPullRoleId
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}
