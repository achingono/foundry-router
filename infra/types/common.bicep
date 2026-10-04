// Shared deployment choices. Public parameters retain their allowed decorators;
// typed internal variables and module contracts consume these exported aliases.
@description('Provision a resource or attach to an existing resource.')
@export()
type ResourceMode = 'new' | 'existing'

@description('Registry pull authentication mechanism.')
@export()
type RegistryAuthMode = 'managedIdentity' | 'secret'
