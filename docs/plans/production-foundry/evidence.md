# Evidence

| Item | Reference | Notes |
|---|---|---|
| Authorization | Current session | Completed local inputs and production deployment authorized; cross-subscription registry noted |
| Runtime review | Shared-credit final independent review | All lifecycle Major findings closed; 125 focused cases/fault replays passed; full444/90.14% implementing evidence |
| Input validation | Operator local values | Six model prices and two resource cycles/estimates validated; 12 backend/six pool/two group Settings accepted |
| Registry tenant/scope | Azure metadata | Deployment and registry subscriptions share tenant; ACR pull scope explicitly registry subscription/RG |
| Secrets | Dedicated new production vault | Eight namespaced secrets populated with captured resource credentials; disjoint auth generated once; no credential values displayed |
| Image | Linux amd64 production build | Built shared-credit image and pushed to cross-subscription ACR; selected application-only Docker COPY instructions exclude local config from image; local inputs also excluded from future build context |
| Template checks | Bicep and Azure | Lint/validation/what-if passed; existing CPU/assertions notices remain; physical resource additions as planned |
| Deployment progress | Azure bootstrap | Initial command timed out while environment provisioned; parent deployment remained Running, not failed |
| Bootstrap/final deployment | Production resource group | Both deployments ultimately Succeeded; console table Analytics/30-day retention; image pulled from cross-subscription registry |
| Runtime configuration | Healthy production app | Exact six selected models, 12 deployment backends, two canonical resource accounts; memory state and min/max1 |
| Authentication | Generated disjoint keys in production vault | Readiness/liveness/model discovery/admin/metrics and role rejection checked without displaying keys |
| Scoped access | Registry and vault | AcrPull on registry in its subscription, Secrets User on production vault; bootstrap redeployment reused grants; temporary operator Secrets Officer removed |
| Limits | Configuration-only production verification | No production inference sent; pricing/credit values are operator-supplied estimates, not Azure balances. Memory state loses accumulated estimates on restart; persistence cut-over remains pending |
| Independent review | Scoped deployment/infra review | No infrastructure Critical/Major issues; stale current production status docs reconciled to completed configuration scope |
