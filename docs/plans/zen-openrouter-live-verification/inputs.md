# Live verification inputs

| Input | Source | Owner |
| --- | --- | --- |
| Backends implementation and mocked evidence | [Zen/OpenRouter plan](../opencode-zen-openrouter/index.md), [evidence](../opencode-zen-openrouter/evidence.md) | Repository |
| Live-verification precedent | [Real Foundry inference](../foundry-inference/index.md), [scoped compatible text live evidence](../google-compatible-signature-text/evidence.md) | Repository |
| Router configuration/API contracts | [Configuration](../../configuration/index.md), [API](../../api/index.md) | Repository |
| Operator-selected exact models (one Zen Responses row, one OpenRouter chat model, one OpenRouter embedding model) | Operator | Operator |
| Operator-approved test prices and budget of at most five dispatches | Operator | Operator |
| Live credentials supplied out of band (env or token-authenticated vault reads) | Operator | Operator |
| Reviewed harness with fixed manifest, durable ledger and bounded transport observer | [Activities](activities.md) | Implementer/reviewer |
| Offline crash/resume, observation and redaction evidence | [Exit criteria](exit-criteria.md) | Implementer/reviewer |

Local implementation needs no live credential. Live stages need the exact
models, test prices, and out-of-band credentials above. Upstream documentation
is informational only and does not establish router compatibility.

Bind the run manifest to the source revision, exact provider roots/models, logical
pools, test prices, request bounds and five case IDs. Store no credentials or
prompt/output text in the manifest; fix request templates in the harness source.
Use a dedicated local run directory outside router memory, initialized once before
dispatch. Missing state for an initialized run must refuse, never silently create
a fresh budget. Local captures remain ignored and must not replace or mutate
historical Google verification ledgers.
