import { RegistryAuthMode } from './common.bicep'
import { StateBackend } from './state.bicep'

@export()
@sealed()
type EnvironmentConfig = {
  name: string
  location: string
  tags: object
  workspaceName: string
}

@export()
@sealed()
type EnvironmentRef = {
  id: string
}

@export()
@sealed()
type RouterSecretUrls = {
  clientKeys: string
  adminKeys: string
  backends: string
  models: string
  pricing: string
  cycleStartDay: string
  cycleAllowance: string
  initialRemaining: string
}

@export()
@sealed()
type RouterRegistryConfig = {
  authMode: RegistryAuthMode
  server: string
  username: string
  isExternalRegistry: bool
}

@export()
@sealed()
type RouterStateConfig = {
  backend: StateBackend
  endpoint: string
  healthTableName: string
  creditTableName: string
}

@export()
@sealed()
type RouterConfig = {
  name: string
  containerName: string
  location: string
  tags: object
  environmentId: string
  image: string
  clientId: string
  containerPort: int
  @minValue(0)
  minReplicas: int
  @minValue(1)
  maxReplicas: int
  secretNamePrefix: string
  secretUrls: RouterSecretUrls
  registry: RouterRegistryConfig
  state: RouterStateConfig
}

@export()
@sealed()
type RouterRef = {
  id: string
  fqdn: string
}
