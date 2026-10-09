# Provider inputs

| Input | Source | Owner |
| --- | --- | --- |
| Roadmap and completed extraction | [Roadmap](../google-ai-routing-order/index.md), [extraction](../openai-compatible-adapter/index.md) | Repository |
| Shared translator/context | `api/adapters/openai_compatible.py` | API |
| Config and egress confinement | `config/__init__.py`, `backends/__init__.py` | Config/backend client |
| Translated lifecycle | `forwarding/__init__.py` | Forwarding |
| Credit/quota and operation filtering | `credit.py`, `ratelimit.py`, `routing/__init__.py` | Accounting/routing |
| Canonical security/API contracts | [Security](../../configuration/security.md), [API](../../api/index.md) | Repository |

Local implementation needs no live credential. Live verification needs operator-selected
exact upstream/model and a finite budget.
