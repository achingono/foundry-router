# OpenAI-Compatible Adapter Extraction Inputs

| Input | Reference | Notes |
| --- | --- | --- |
| Current adapter | [google_ai_studio.py](../../../src/foundry_router/api/adapters/google_ai_studio.py) | ~1,340 lines mixing generic Chat Completions translation and Google profile hooks |
| Adapter protocol | [base.py](../../../src/foundry_router/api/adapters/base.py) | `ProviderAdapter` protocol is unchanged |
| Subclasses | [google_native.py](../../../src/foundry_router/api/adapters/google_native.py), [google_audio_output.py](../../../src/foundry_router/api/adapters/google_audio_output.py), [google_signed.py](../../../src/foundry_router/api/adapters/google_signed.py) | Depend on `_check_responses_request`, `_translate_responses_success`, decoder private state (`_handle_payload`, `_context`, `_call_fragments`, …) |
| Google-specific helpers | [google_tools.py](../../../src/foundry_router/api/adapters/google_tools.py) | `request_context`, `requested_features`, `build_messages`, `translate_calls` remain Google-owned |
| Contract | [adapter contract](../google-ai-studio-adapter/adapter-contract.md), ADR-008 | Wire behavior must stay byte-identical |
| Tests | `tests/unit/test_google_adapter.py`, `test_google_review_contracts.py`, `test_google_tools_multimodal.py`, `test_google_lifecycle.py`, integration suites | Regression oracle; imports of `GoogleAiStudioAdapter`, `GoogleStreamDecoder`, `MAX_GOOGLE_EVENT_BYTES` must keep working |
