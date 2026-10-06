# Signed continuation inputs

**Planned**, drafted2026-10-05 before runtime changes. Parent scope remains required.

| Input | Source | Validation |
| --- | --- | --- |
| Public extension and trust requirements | [Parent contract](../capability-contract.md#thought-signatures-and-continuation-state) | Versioned opt-in state; caller/history/backend binding; independent billing |
| Native Part protocol | [generateContent reference](https://ai.google.dev/api/generate-content#Part) | thoughtSignature is optional opaque base64 bytes attached to a Part |
| Protocol distinction | [Thinking guide](https://ai.google.dev/gemini-api/docs/thinking) | Guide distinguishes Interactions thought steps from generateContent Part metadata; use only generateContent |
| Exact public client | OpenAI Python2.8.1 | Nonstream model validation and actual ResponseStreamState final snapshot retain extra fields and model_dump replay; synthetic proof completed |
| Current boundaries | auth/config/API/adapter/routing/forwarding | Raw credential currently returned internally; no state/principal service exists |

Exact operator model IDs and live signature association remain pending. No provider calls or
secret reads. Credential reference and separate free-tier projects recorded in parent evidence.
