// Public deployment choices. Credentials are supplied separately as secure parameters.
@export()
@sealed()
type NewAcr = {
  mode: 'new'
  @minLength(5)
  @maxLength(50)
  name: string
}

@export()
@sealed()
type ExistingAcr = {
  mode: 'existing'
  @minLength(5)
  @maxLength(50)
  name: string
  @minLength(1)
  resourceGroup: string
}

@export()
@discriminator('mode')
type AcrLifecycle = NewAcr | ExistingAcr

@export()
@sealed()
type ManagedIdentityAuth = {
  mode: 'managedIdentity'
}

@export()
@sealed()
type SecretAuth = {
  mode: 'secret'
  @minLength(1)
  username: string
}

@export()
@discriminator('mode')
type AcrAuth = ManagedIdentityAuth | SecretAuth

@export()
@sealed()
type AcrRegistry = {
  kind: 'acr'
  acr: AcrLifecycle
  auth: AcrAuth
}

@export()
@sealed()
type ExternalRegistry = {
  kind: 'external'
  @minLength(1)
  server: string
  @minLength(1)
  username: string
}

@export()
@discriminator('kind')
type DeploymentRegistry = AcrRegistry | ExternalRegistry

@export()
@sealed()
type NewVault = {
  mode: 'new'
  @minLength(3)
  @maxLength(24)
  name: string
}

@export()
@sealed()
type ExistingVault = {
  mode: 'existing'
  @minLength(3)
  @maxLength(24)
  name: string
  @minLength(1)
  resourceGroup: string
}

@export()
@discriminator('mode')
type VaultLifecycle = NewVault | ExistingVault

@export()
@sealed()
type NewStorage = {
  mode: 'new'
  @minLength(3)
  @maxLength(24)
  name: string
}

@export()
@sealed()
type ExistingStorage = {
  mode: 'existing'
  @minLength(3)
  @maxLength(24)
  name: string
  @minLength(1)
  resourceGroup: string
}

@export()
@discriminator('mode')
type StorageLifecycle = NewStorage | ExistingStorage

@export()
@sealed()
type MemoryState = {
  backend: 'memory'
}

@export()
@sealed()
type TableState = {
  backend: 'table'
  account: StorageLifecycle
  @minLength(3)
  @maxLength(50)
  tablePrefix: string?
}

@export()
@discriminator('backend')
type DeploymentState = MemoryState | TableState
