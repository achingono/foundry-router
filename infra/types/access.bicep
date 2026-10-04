@description('Registry name resolved in the access module deployment scope.')
@export()
@sealed()
type RegistryPullConfig = {
  registryName: string
}

@description('Vault name resolved in the access module deployment scope.')
@export()
@sealed()
type VaultSecretsConfig = {
  keyVaultName: string
}
