# Phase 02 Risk Register

## Risks

| ID | Risk | Impact | Mitigation | Status |
| --- | --- | --- | --- | --- |
| R1 | Backend URL or credential handling bypasses the Phase 01 security boundary | Secret disclosure or unintended egress | Centralize backend target construction and test hostile URLs/headers | Open |
| R2 | Streaming is buffered or retried after output begins | Latency, memory growth, or duplicate model output | Use `StreamingResponse` over the backend stream and explicitly exclude retries | Open |
| R3 | Azure backend protocol paths differ by deployment type | Requests fail against configured deployments | Explicitly target deployment-scoped Azure OpenAI-compatible paths and make API version configurable | Mitigated |
| R4 | Upstream error bodies contain sensitive content | Secret or prompt leakage in client responses/logs | Pass only bounded protocol responses and never log bodies | Open |

## Open Decisions
- The supported Phase 02 protocol is deployment-scoped Azure OpenAI-compatible Responses and embeddings with configurable API version; other endpoint flavors remain out of scope.
