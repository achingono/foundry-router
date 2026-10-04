targetScope = 'resourceGroup'

import { ObservabilityConfig, ObservabilityRef } from '../types/observability.bicep'

param config ObservabilityConfig

resource workspace 'Microsoft.OperationalInsights/workspaces@2021-06-01' = {
  name: config.workspaceName
  location: config.location
  tags: config.tags
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
    workspaceCapping: { dailyQuotaGb: config.dailyCapGb }
  }
}

// Bootstrap false until ingestion has created the Classic console-log table.
resource consoleLogsTable 'Microsoft.OperationalInsights/workspaces/tables@2022-10-01' = if (config.configureConsoleLogsPlan) {
  parent: workspace
  name: 'ContainerAppConsoleLogs_CL'
  properties: {
    plan: config.consoleLogsPlan
    totalRetentionInDays: 30
  }
}

resource actionGroup 'Microsoft.Insights/actionGroups@2023-01-01' = {
  name: config.actionGroupName
  location: 'global'
  tags: config.tags
  properties: {
    groupShortName: 'routercost'
    enabled: true
    emailReceivers: [
      {
        name: 'daily-cap-owner'
        emailAddress: config.alertEmailAddress
        useCommonAlertSchema: true
      }
    ]
  }
}

resource dailyCapAlert 'Microsoft.Insights/scheduledQueryRules@2023-03-15-preview' = {
  name: config.alertName
  location: config.location
  tags: config.tags
  properties: {
    displayName: config.alertDisplayName
    description: 'Fires when billable ingestion approaches the daily cap so the cause can be investigated before the cap stops ingestion.'
    severity: 2
    enabled: true
    evaluationFrequency: 'PT1H'
    windowSize: 'P1D'
    scopes: [workspace.id]
    criteria: {
      allOf: [
        {
          query: 'Usage | where IsBillable and TimeGenerated >= ago(1d) | summarize BillableGB = sum(Quantity) / 1000 | where BillableGB >= ${config.dailyCapGb} * 0.9'
          timeAggregation: 'Count'
          operator: 'GreaterThanOrEqual'
          threshold: 1
          failingPeriods: {
            numberOfEvaluationPeriods: 1
            minFailingPeriodsToAlert: 1
          }
        }
      ]
    }
    actions: {
      actionGroups: [actionGroup.id]
      customProperties: {}
    }
  }
}

// Logging shared keys stay in the owning environment configuration, not outputs.
output workspaceRef ObservabilityRef = {
  workspaceId: workspace.id
  workspaceName: workspace.name
}
