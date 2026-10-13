# Accepted OpenRouter staging models

Status: **Implemented and deployed; historical non-streaming public/admin acceptance passed**.

Use these exact logical model names with the existing staging Responses endpoint and staging client authentication:

| Request model | OpenRouter deployment | Mode |
| --- | --- | --- |
| `gpt-6-luna-or` | `openai/gpt-6-luna` | Non-streaming Responses |
| `claude-haiku-5.5-or` | `anthropic/claude-haiku-5.5` | Non-streaming Responses |

Set `stream: false`. Both share the canonical `or-shared` credit account.
The historical run verified completion, coherent usage, local debit and cleared reservations. See [source evidence](../production-zen-openrouter/evidence-roster-2026-10-12.md).

Fresh read-only checks on October 12, 2026 verified revision `foundry-router-staging--0000002`, exact backend/deployment/group bindings, live/ready health, and zero active/inflight reservations. A successful readback does not guarantee ongoing availability; prior intermittent health timeouts remain recorded.

DeepSeek,MiMo and Spark are excluded from this accepted new roster. This selection is documentation, not an enforced runtime allow-list; their existing staging configurations remain. Existing unrelated pools are unchanged. No new inference,configuration write,restart or production promotion was performed. Streaming and production qualification remain open.
