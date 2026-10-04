@export()
@sealed()
type RuntimeIdentityConfig = {
  name: string
  location: string
  tags: object
}

@export()
@sealed()
type RuntimeIdentityRef = {
  id: string
  clientId: string
  principalId: string
}
