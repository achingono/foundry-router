# Production Rollout Inputs

| Input | Source | Owner |
| --- | --- | --- |
| Reviewed implementation and behavior | [Alias plan](../model-aliases/index.md), runtime/tests | Contributor |
| Production target | Read-only Azure Container Apps discovery; installed client provider URL | Operator |
| Deployment baseline | Live image/revision, scaling, registry and vault references | Azure |
| Build and CI | Existing GitHub CI; remote ACR build if local Docker unavailable | Contributor |
| Authentication | Existing environment client key; scoped vault access for admin key if needed | Operator |
| Approval client | Installed codex-cli 0.160.0; official [Auto-review documentation](https://developers.openai.com/codex/sandboxing/auto-review) | Client |

No secret values or real resource IDs belong in committed evidence. The operator supplied `infra/production-inputs.local.json`; derive gitignored typed ARM parameters from it and the successful deployment metadata, rather than placeholder examples.
