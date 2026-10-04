@export()
@sealed()
type NewRegistryConfig = {
  name: string
  location: string
  tags: object
  grantPull: bool
}

@export()
@sealed()
type RegistryRef = {
  id: string
  loginServer: string
}

@export()
@sealed()
type NewVaultConfig = {
  name: string
  location: string
  tags: object
}

@export()
@sealed()
type VaultRef = {
  id: string
  uri: string
}
