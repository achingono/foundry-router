# Zen/OpenRouter inputs

| Input | Source | Owner |
| --- | --- | --- |
| Router/architecture contracts | [Architecture](../../architecture/index.md), [solution structure](../../architecture/solution-structure.md) | Repository |
| Runtime/policy contracts | [Features](../../features/index.md), [routing](../../features/routing.md) | Repository |
| Public API/auth contract | [API](../../api/index.md) | Repository |
| Configuration/security contracts | [Configuration](../../configuration/index.md), [security](../../configuration/security.md) | Repository |
| Generic provider precedent | [Compatible provider](../openai-compatible-provider/index.md), [adapter extraction](../openai-compatible-adapter/index.md) | Repository |
| Shared translator/context | `src/foundry_router/api/adapters/openai_compatible.py`, `compatible_text.py` | API |
| Pass-through precedent | `src/foundry_router/api/adapters/azure.py` | API |
| Adapter registry | `src/foundry_router/api/adapters/__init__.py` | API |
| Config and egress confinement | `src/foundry_router/config/__init__.py`, `src/foundry_router/backends/__init__.py` | Config/backend client |
| Translated/passthrough lifecycle | `src/foundry_router/forwarding/__init__.py` | Forwarding |
| Credit/quota and operation filtering | `credit.py`, `ratelimit.py`, `routing/__init__.py` | Accounting/routing |
| Zen endpoint table (Responses subset) | `https://opencode.ai/docs/zen/` (fetched 2026-10-09; Responses rows use `@ai-sdk/openai` at `https://opencode.ai/zen/v1/responses`) | Upstream docs |
| OpenRouter request/headers contract | `https://openrouter.ai/docs` (fetched 2026-10-09; `POST /api/v1/chat/completions`, Bearer + optional attribution headers) | Upstream docs |

Local implementation needs no live credential. Live verification needs
operator-selected exact upstream/model and a finite budget. Upstream docs are
informational only and do not establish router compatibility.
