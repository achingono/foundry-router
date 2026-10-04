targetScope = 'resourceGroup'

import { EnvironmentConfig, EnvironmentRef } from '../../types/containers.bicep'

param config EnvironmentConfig

resource workspace 'Microsoft.OperationalInsights/workspaces@2021-06-01' existing = {
  name: config.workspaceName
}

resource environment 'Microsoft.App/managedEnvironments@2023-04-01-preview' = {
  name: config.name
  location: config.location
  tags: config.tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: workspace.properties.customerId
        sharedKey: workspace.listKeys().primarySharedKey
      }
    }
  }
}

// Workspace credentials remain solely in environment configuration.
output environmentRef EnvironmentRef = {
  id: environment.id
}
