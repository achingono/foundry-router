# Observability and Troubleshooting

## Status: Design Target

Use structured JSON logs and a correlation/request ID. Record request ID, model, backend, endpoint type, status, latency, tokens, estimated cost, retry count, streaming flag, routing state, and routing score. Do not record prompts or responses by default.

## Metrics

Measure requests by model/backend and outcome, 429s, latency and time to first token, input/output tokens, estimated spend by model/backend, estimated remaining credit, and backend states including active, conservation, protected, cooldown, and disabled.

## Operator Checks

When a request fails, inspect model configuration, candidate availability, backend state, cooldown expiry, quota signals, credit estimate and reserve, cost-data age, and retry count. Distinguish upstream errors from router validation errors. Administrative status must never reveal credentials.

## Cost and Credit Warnings

Estimated spend is not authoritative Azure cost. A stale reconciliation state or negative estimate must be visible. If all candidates are protected or a conservative request reservation cannot fit, return an explicit safe-capacity error rather than silently routing unsafely.
