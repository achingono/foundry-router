@export()
@sealed()
type ObservabilityConfig = {
  workspaceName: string
  actionGroupName: string
  alertName: string
  alertDisplayName: string
  location: string
  tags: object
  @minValue(1)
  @maxValue(1000)
  dailyCapGb: int
  alertEmailAddress: string
  consoleLogsPlan: 'Analytics'
  configureConsoleLogsPlan: bool
}

@export()
@sealed()
type ObservabilityRef = {
  workspaceId: string
  workspaceName: string
}
