# Google AI Studio capacity inventory inputs

| Input | Source | Owner |
| --- | --- | --- |
| Five project catalogs | [Discovery](../google-ai-studio-tools-multimodal/live-discovery-actual.json) | Recorded validation |
| Free-tier text classification | [Discovered manifest](../google-ai-studio-tools-multimodal/live-runner/manifest-discovered.json) | Recorded validation |
| Dated outcomes and limitations | [Live evidence](../google-ai-studio-tools-multimodal/live-runner/evidence.md) | Recorded validation |
| Attempt identity and usage | Three dated ledgers in the live-runner folder | Recorded validation |
| Operator quota screenshots/project IDs | Captured inputs (local-only `quotas.md`) | Operator |
| Quota semantics | [Configuration](../../configuration/index.md), [routing](../../features/routing.md) | Repository |

Required for quota completion: current per-project/model RPM, input TPM, RPD, tier, capture date and source from the authenticated AI Studio rate-limit page. Provider violations capture some model dimensions. Operator screenshots now supply all project IDs and selected-model displayed limits; operator confirms free-tier. Shared groups, UI TPM dimension, capture timestamp and independent tier/credential mapping remain uncaptured. No credentials or resource IDs are inferred from project labels.
