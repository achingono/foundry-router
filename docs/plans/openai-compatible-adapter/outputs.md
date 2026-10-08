# OpenAI-Compatible Adapter Extraction Outputs

| Output | Location | Verification |
| --- | --- | --- |
| Generic adapter and decoder | `src/foundry_router/api/adapters/openai_compatible.py` | New focused unit tests |
| Baseline characterization fixtures/tests | `tests/unit/` and existing Google fixture conventions | Pass before and after extraction with identical expectations and deterministic UUID/time values |
| Thin Google subclass | `src/foundry_router/api/adapters/google_ai_studio.py` | Unchanged Google unit/integration suites |
| Package export | `src/foundry_router/api/adapters/__init__.py` | Import tests |
| Documentation | [architecture](../../architecture/index.md), [solution structure](../../architecture/solution-structure.md), this plan | Link check |
