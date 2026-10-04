targetScope = 'resourceGroup'

import { RuntimeIdentityConfig, RuntimeIdentityRef } from '../types/identity.bicep'

param config RuntimeIdentityConfig

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: config.name
  location: config.location
  tags: config.tags
}

output identityRef RuntimeIdentityRef = {
  id: identity.id
  clientId: identity.properties.clientId
  principalId: identity.properties.principalId
}
