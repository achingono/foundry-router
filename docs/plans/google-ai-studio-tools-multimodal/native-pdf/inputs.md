# Native/PDF inputs

- [Full requirement audit](../completion-audit.md), current adapter/transport/routing lifecycle.
- [Google native reference](https://ai.google.dev/api/generate-content), fetched2026-10-05:
  contents/parts inlineData, functionCall/id, functionResponse/id, usageMetadata totals and SSE.
- [Document processing](https://ai.google.dev/gemini-api/docs/document-processing), fetched2026-10-05:
  inlinePDF,258 tokens/page, documented page/bytes limits (router will use lower caps).
- [Compatibility](https://ai.google.dev/gemini-api/docs/openai), fetched2026-10-05:
  no verified inlinePDF mapping; current signatures link returned minimal page.
- Existing OpenAI Python2.8.1 real stream-state fixtures and conservative billing/credit tests.
- Exact native model/thinking-disable capability and token-price affirmation: operator gate,
  not inferred from model names. Live credentials/spend not supplied.
- pypdf dependency/version/resource-worker review required before PDF parsing code.
