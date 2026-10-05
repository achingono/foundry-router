# Model Alias Outputs

## Mandatory Outputs

| Output | Description | Format |
| --- | --- | --- |
| Validated configuration/resolver | Explicit one-hop map, no defaults/overrides/chains, immutable identity context | Python and tests |
| API integration | Canonical request routing and settlement for Responses/embeddings, original payload preserved | Python and regression tests |
| Discovery and diagnostics | Alias catalog/admin mapping, requested/resolved logs and canonical metrics/readiness | API/telemetry tests and docs |
| Deployment configuration | Optional root/typed/container environment plumbing, empty default, no new resources | Bicep, examples and render checks |
| Documentation | Configuration, API semantics, architecture, routing, security, observability, traceability and operations | Markdown |
| Code evidence | Coverage/tests/lint/type/build/template results and independent reviews | [Evidence](evidence.md) |

## Optional Outputs
- Separate bounded live-inference and actual approval-client validation evidence.
- Additional custom alias examples referencing existing canonical pools.

## Output Quality Checklist
- [ ] Mandatory implementation outputs produced and independently reviewed.
- [ ] Evidence distinguishes plan, code, live route and approval-client correctness.
- [ ] No alias is presented as a newly deployed or equivalent specialized model.
