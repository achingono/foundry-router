# Google AI Studio Adapter Outputs

## Mandatory Outputs

| Output | Description | Format |
| --- | --- | --- |
| Provider contract | Verified field/event matrix, unsupported-feature behavior, source dates and ADR | Markdown and synthetic fixtures |
| Provider adapters | Typed protocol, Azure pass-through and Google request/response/SSE translation | Python in proposed `api/adapters/` |
| Routing/configuration integration | Supported-operation validation and identical eligibility on initial selection/failover | Python and config examples |
| Accounting integration | Embeddings quota wiring, full supported-input estimates, attempt accounting and billable-protocol-failure settlement | Python and lifecycle tests |
| Bounded forwarding | Incremental SSE framing, success/error body limits and independent cleanup | Python and stream tests |
| Regression tests | Strict provider schemas, Azure pass-through, unsupported requests, errors, security and quota/credit behavior | pytest fixtures/unit/integration tests |
| Canonical documentation | API subset, SSE examples, configuration, operations, observability, architecture and traceability | Markdown |
| Verification evidence | Independent reviews, test/coverage/lint/type/build results, gate limitations | [Evidence](evidence.md) |

## Optional Outputs

- Opt-in Google smoke test and redacted evidence for real text, streaming and embeddings.
- A verified text-only client example; no claim of tool-dependent agent compatibility.

## Output Quality Checklist

- [ ] All mandatory implementation outputs produced.
- [ ] Outputs independently reviewed before the code gate.
- [ ] Evidence records actual command results and exact live-validation scope separately.
