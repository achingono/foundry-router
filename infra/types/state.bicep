@description('Router credit/health state backend; quota accounting remains process-local.')
@export()
type StateBackend = 'memory' | 'table'

@description('Storage account and router table names, without credentials.')
@export()
@sealed()
type StorageTableNames = {
  storageAccountName: string
  healthTableName: string
  creditTableName: string
}

@description('New Storage account configuration in the deployment resource group.')
@export()
@sealed()
type NewStorageAccountConfig = {
  names: StorageTableNames
  location: string
  tags: object
}

@description('Router tables in an existing account resolved in the module scope.')
@export()
@sealed()
type ExistingStorageTablesConfig = {
  names: StorageTableNames
}

@description('Resolved non-secret Azure Table endpoint.')
@export()
@sealed()
type TableEndpointOutput = {
  tableEndpoint: string
}
