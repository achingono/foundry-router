# OpenAI-Compatible Adapter Extraction Risk Register

## Risks

| ID | Risk | Impact | Mitigation | Status |
| --- | --- | --- | --- | --- |
| R1 | Silent wire/event change during the move | Client-visible regressions, settlement drift | Move code verbatim; existing suites unchanged as oracle | Open |
| R2 | Subclasses rely on private names that get renamed | Native/audio/signed adapters break | Preserve every private attribute and method name used by subclasses | Open |
| R3 | Base class gives a permissive default context | Future provider egresses unvalidated tools/schemas | Context/message/call hooks raise `NotImplementedError` | Open |
| R4 | Import cycle between adapter modules | Startup failure | Generic module imports only `base`; Google imports generic | Open |
| R5 | Label drift changes public 422 messages | Client contract change | `provider_label = "Google"`; tests compare messages | Open |

## Open Decisions

- Whether to add a configurable `openai_compatible` provider is deferred to a separate plan
  with its own credential, endpoint and capability contract.
