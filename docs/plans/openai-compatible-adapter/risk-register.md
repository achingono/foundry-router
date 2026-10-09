# OpenAI-Compatible Adapter Extraction Risk Register

## Risks

| ID | Risk | Impact | Mitigation | Status |
| --- | --- | --- | --- | --- |
| R1 | Silent wire/event change during the move | Client-visible regressions, settlement drift | Capture deterministic complete rejection/body/SSE fixtures before extraction; run unchanged afterward alongside existing suites | Mitigated locally |
| R2 | Subclasses rely on private names that get renamed | Native/audio/signed adapters break | Preserve every private attribute and method name used by subclasses | Mitigated locally |
| R3 | Base class gives a permissive default context | Future provider egresses unvalidated tools/schemas | Context/message/call hooks raise `NotImplementedError` | Mitigated locally |
| R4 | Import cycle between adapter modules | Startup failure | Generic module imports only `base`; Google imports generic | Mitigated locally |
| R5 | Label drift changes public 422 messages | Client contract change | `provider_label = "Google"`; tests compare messages | Mitigated locally |
| R6 | Shared protocol widens `_context` and loses concrete Google methods | Strict mypy fails or native argument validation is weakened | Read-only protocol; context-parameterized adapter/decoder bases specialized with `GoogleRequestContext`; retain native `validate_arguments` unchanged | Mitigated locally |
| R7 | Import-isolation gate conflicts with existing media annotations or package initialization | Unnecessary protocol/package refactor or misleading isolation claim | Gate direct runtime imports only; explicit type-only `PreparedGoogleMedia` exception; transitive package imports remain outside scope | Mitigated locally |

## Open Decisions

- Whether to add a configurable `openai_compatible` provider is deferred to a separate plan
  with its own credential, endpoint and capability contract.
