// Scoped Key Vault Secrets User role assignment for an existing vault in another resource group.
targetScope = 'resourceGroup'

import { VaultSecretsConfig } from '../types/access.bicep'

@description('Name of the existing key vault.')
param config VaultSecretsConfig

@description('Principal ID of the pre-created container app runtime identity.')
param principalId string

@description('Deterministic suffix for the role assignment name.')
param assignmentSuffix string = uniqueString(resourceGroup().id, config.keyVaultName, principalId)

// Key Vault Secrets User built-in role (tenant-independent GUID).
var secretsUserRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '4633458b-17de-408a-b874-0445c86b69e6'
)

resource existingVault 'Microsoft.KeyVault/vaults@2023-02-01' existing = {
  name: config.keyVaultName
}

resource secretsUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, existingVault.id, principalId, secretsUserRoleId, assignmentSuffix)
  scope: existingVault
  properties: {
    roleDefinitionId: secretsUserRoleId
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}
