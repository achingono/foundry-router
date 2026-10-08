# Google AI Studio capacity inventory inputs

| Input | Source | Owner |
| --- | --- | --- |
| Five project catalogs | [Discovery](../google-ai-studio-tools-multimodal/live-discovery-actual.json) | Recorded validation |
| Free-tier text classification | [Discovered manifest](../google-ai-studio-tools-multimodal/live-runner/manifest-discovered.json) | Recorded validation |
| Dated outcomes and limitations | [Live evidence](../google-ai-studio-tools-multimodal/live-runner/evidence.md) | Recorded validation |
| Attempt identity and usage | Three dated ledgers in the live-runner folder | Recorded validation |
| Quota semantics | [Configuration](../../configuration/index.md), [routing](../../features/routing.md) | Repository |

Required for quota completion: current per-project/model RPM, input TPM, RPD, tier, capture date and source from the authenticated AI Studio rate-limit page. Some model dimensions are now captured from live provider quota violations; actual project IDs, current tier and remaining quotas are missing. Operator input requested. No credentials or resource IDs will be inferred from project labels.
