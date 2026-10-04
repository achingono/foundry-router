// Phase 11: tables + data-plane role assignments on a Storage account in its own resource group.
// Used for existing accounts in another resource group (declaring child tables and
// role assignments requires the target scope); new accounts use storageAccountResources.bicep.
targetScope = 'resourceGroup'

import { ExistingStorageTablesConfig } from '../types/state.bicep'

@description('Name of the Storage account holding the router tables.')
param config ExistingStorageTablesConfig

@description('Principal ID of the pre-created container app runtime identity.')
param principalId string

@description('Deterministic suffix for the role assignment names.')
param assignmentSuffix string = uniqueString(
  resourceGroup().id,
  config.names.storageAccountName,
  config.names.healthTableName,
  config.names.creditTableName,
  principalId
)

// Storage Table Data Contributor built-in role (tenant-independent GUID from
// Microsoft built-in roles reference; confirm with:
// az role definition list --name 'Storage Table Data Contributor' --query '[].name').
var tableDataContributorRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '0a9a7e1f-b9d0-4cc4-a60d-0319b160acf8'
)

resource account 'Microsoft.Storage/storageAccounts@2023-01-01' existing = {
  name: config.names.storageAccountName
}

resource tableService 'Microsoft.Storage/storageAccounts/tableServices@2023-01-01' existing = {
  parent: account
  name: 'default'
}

resource healthTable 'Microsoft.Storage/storageAccounts/tableServices/tables@2023-01-01' = {
  parent: tableService
  name: config.names.healthTableName
}

resource creditTable 'Microsoft.Storage/storageAccounts/tableServices/tables@2023-01-01' = {
  parent: tableService
  name: config.names.creditTableName
}

resource healthTableRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, healthTable.id, principalId, tableDataContributorRoleId, assignmentSuffix)
  scope: healthTable
  properties: {
    roleDefinitionId: tableDataContributorRoleId
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}

resource creditTableRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, creditTable.id, principalId, tableDataContributorRoleId, assignmentSuffix)
  scope: creditTable
  properties: {
    roleDefinitionId: tableDataContributorRoleId
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}
