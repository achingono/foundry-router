# Live verification inputs

| Input | Source | Owner |
| --- | --- | --- |
| Backends implementation and mocked evidence | [Zen/OpenRouter plan](../opencode-zen-openrouter/index.md), [evidence](../opencode-zen-openrouter/evidence.md) | Repository |
| Live-verification precedent | [Real Foundry inference](../foundry-inference/index.md), [scoped compatible text live evidence](../google-compatible-signature-text/evidence.md) | Repository |
| Router configuration/API contracts | [Configuration](../../configuration/index.md), [API](../../api/index.md) | Repository |
| Operator-selected exact models (one Zen Responses row, one OpenRouter chat model, one OpenRouter embedding model) | Operator | Operator |
| Operator-approved test prices and finite dispatch budget | Operator | Operator |
| Live credentials supplied out of band (env or token-authenticated vault reads) | Operator | Operator |

Local implementation needs no live credential. Live stages need the exact
models, test prices, and out-of-band credentials above. Upstream documentation
is informational only and does not establish router compatibility.
