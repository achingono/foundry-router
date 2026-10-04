targetScope = 'resourceGroup'

import { NewVaultConfig, VaultRef } from '../types/resources.bicep'

param config NewVaultConfig
param identityResourceId string
param principalId string

resource vault 'Microsoft.KeyVault/vaults@2023-02-01' = {
  name: config.name
  location: config.location
  tags: config.tags
  properties: {
    tenantId: subscription().tenantId
    sku: { family: 'A', name: 'standard' }
    enabledForDeployment: true
    enabledForTemplateDeployment: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 90
    enableRbacAuthorization: true
  }
}

resource secretsUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, vault.id, identityResourceId, '4633458b-17de-408a-b874-0445c86b69e6')
  scope: vault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}

output vaultRef VaultRef = {
  id: vault.id
  uri: vault.properties.vaultUri
}
