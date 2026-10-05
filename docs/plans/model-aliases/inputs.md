# Model Alias Inputs

## Required Inputs

| Input | Source | Owner |
|---|---|---|
| Canonical contracts | [Architecture](../../architecture/index.md), [API](../../api/index.md), [configuration](../../configuration/index.md), [security](../../configuration/security.md), [routing](../../features/routing.md) | Runtime contributor |
| Current namespace and physical mapping | [Settings](../../../src/foundry_router/config/__init__.py), [API routes](../../../src/foundry_router/api/routes/openai.py), [backend client](../../../src/foundry_router/backends/__init__.py) | Config/API contributor |
| Admission, settlement and telemetry | [Routing](../../../src/foundry_router/routing/__init__.py), [forwarding](../../../src/foundry_router/forwarding/__init__.py), [API common](../../../src/foundry_router/api/common.py), [credit](../../../src/foundry_router/credit.py), [metrics](../../../src/foundry_router/metrics/__init__.py) | Runtime contributor |
| Existing regressions | [Config tests](../../../tests/unit/test_config.py), [main tests](../../../tests/unit/test_main.py), [backend tests](../../../tests/unit/test_backends.py), [stream tests](../../../tests/unit/test_forwarding_stream.py), [integration](../../../tests/integration/test_full_flow.py) | Test contributor |
| Target evidence | [Production inference](../production-inference/evidence.md) | Operator; historical fs-swarm scope only |
| Deployment configuration | [Root Bicep](../../../infra/main.bicep), [typed adapter](../../../infra/typed.bicep), [container module](../../../infra/modules/containers/router.bicep), [infra guide](../../../infra/README.md) | Infrastructure contributor |
| Quality requirements | [Testing](../../development/testing.md), [CI](../../../.github/workflows/ci.yml), [deep-review prompt](../../../.agents/prompts/deep-review.prompt.md) | Reviewer |

## User-Supplied Background

- [Codex issue 24879](https://github.com/openai/codex/issues/24879)
- [Codex model catalog](https://github.com/openai/codex/blob/main/codex-rs/models-manager/models.json)
- [Codex model metadata](https://github.com/openai/codex/blob/main/codex-rs/protocol/src/openai_models.rs)
- [Codex issue 47916](https://github.com/openai/codex/issues/47916)

These references and the asserted `auto_review_model_override` behavior were supplied by the
user; their current contents were not verified during drafting. The general alias design depends
on the observed naming failure and router contracts, not an assumed Codex setting or issue status.
Verify the actual client version/request contract before claiming reviewer compatibility.

## Optional Inputs

- Additional explicit aliases and operator-selected canonical targets.
- Bounded synthetic approval-client cases with expected allow, deny and error dispositions.
- Live-only configuration/credential references and request/token/spend limits.

## Input Validation Checklist
- [x] Clean tree at `333db5e`, canonical docs, source and affected tests inspected.
- [x] Actual error name distinguished from the additional user-requested alias.
- [x] Independent review completed and findings addressed.
- [ ] Target pool and client contract reverified before live enablement.
