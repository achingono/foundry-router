// New Storage account, tables and table-scoped grants. Called only in Table mode
// so ARM does not validate disabled storage references in the root deployment.
targetScope = 'resourceGroup'

param storageAccountName string
param healthTableName string
param creditTableName string
param principalId string
param identityResourceId string
param location string = resourceGroup().location
param tags object

var tableDataContributorRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '0a9a7e1f-b9d0-4cc4-a60d-0319b160acf8'
)

resource account 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: storageAccountName
  location: location
  tags: tags
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    allowSharedKeyAccess: false
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    allowBlobPublicAccess: false
  }
}

resource tableService 'Microsoft.Storage/storageAccounts/tableServices@2023-01-01' existing = {
  parent: account
  name: 'default'
}

resource healthTable 'Microsoft.Storage/storageAccounts/tableServices/tables@2023-01-01' = {
  parent: tableService
  name: healthTableName
}

resource creditTable 'Microsoft.Storage/storageAccounts/tableServices/tables@2023-01-01' = {
  parent: tableService
  name: creditTableName
}

resource healthTableRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  // Preserve the original root-template assignment GUID inputs exactly.
  name: guid(resourceGroup().id, healthTable.id, identityResourceId, tableDataContributorRoleId)
  scope: healthTable
  properties: {
    roleDefinitionId: tableDataContributorRoleId
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}

resource creditTableRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, creditTable.id, identityResourceId, tableDataContributorRoleId)
  scope: creditTable
  properties: {
    roleDefinitionId: tableDataContributorRoleId
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}

// No storage credentials are returned; the app uses its managed identity.
output tableEndpoint string = account.properties.primaryEndpoints.table
