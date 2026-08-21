# ADR-003: Structured JSON Logging with Automatic Redaction

## Status
Accepted

## Context
The router must provide observability while maintaining security:
- Structured logs for querying/alerting (Azure Monitor, Log Analytics)
- Correlation IDs for request tracing across services
- **No secrets, credentials, prompts, or model outputs in logs**
- Redaction must be tested, not assumed

## Decision
We will use **structlog** with:
- JSON output to stdout (Container Apps captures stdout)
- Contextvars for correlation ID propagation
- Custom redaction processor that recursively scrubs:
  - Known sensitive field names (authorization, api_key, prompt, completion, etc.)
  - Regex patterns for Bearer tokens, API keys, JWTs
- Redaction applied at log event level (processor in structlog pipeline)

Log schema includes:
- `request_id` (correlation ID)
- `timestamp` (ISO 8601 UTC)
- `level`
- `event`
- `model`, `backend`, `endpoint_type`
- `status`, `latency_ms`
- `tokens_in`, `tokens_out`, `estimated_cost_usd`
- `retry_count`, `streaming`
- `routing_state`, `routing_score`

## Consequences

### Positive
- Structured JSON enables KQL queries in Log Analytics
- Automatic redaction reduces risk of accidental secret exposure
- Correlation IDs enable end-to-end tracing
- Standard library logging compatible (can forward to other handlers)
- Redaction logic is testable with unit tests

### Negative
- Redaction adds minimal CPU overhead per log event
- Structured logging requires discipline (use `logger.info("event", key=val)` not f-strings)
- Regex-based redaction may miss novel secret formats (mitigated by field-name-based approach); raw exception messages are not logged

### Neutral
- Log volume increases with structured fields (acceptable for low-traffic proxy)
- Requires structlog knowledge for custom processors

## Alternatives Considered
- **Standard library logging + custom formatter**: More boilerplate, no contextvars integration
- **Loguru**: Nice API but less standard for JSON/observability pipelines
- **OpenTelemetry Python SDK**: Overkill for logging only; use for metrics/tracing later
- **Manual redaction per log call**: Error-prone, not enforceable

## Related
- ADR-001: Python/FastAPI stack
- ADR-004: Secret handling

## References
- structlog documentation: https://www.structlog.org/
- Azure Monitor structured logs: https://learn.microsoft.com/azure/azure-monitor/logs/structured-logging
