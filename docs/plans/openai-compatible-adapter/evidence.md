# OpenAI-Compatible Adapter Extraction Evidence

## Status

**Planned** (2026-10-08).

## Evidence Log

| Item | Reference | Notes |
| --- | --- | --- |
| Baseline | `git status --short`; HEAD `043603b` | Clean tree |
| Templates | [Templates](../../templates/index.md) | Copied into this directory |
| Initial plan review | Independent review session, 2026-10-08 | **Approved with conditions.** Conditions folded into [activities](activities.md) step 5: enumerated preserved private surface (Critical — inherited, so accessible, but now explicit), no `__slots__` for forwarding's dynamic `prefetch_finished` (Major), Google decoder keeps optional context and all creation sites pass it (Major), duck-typed `finish_at_prefetch_eof` untouched (Minor), constant/class re-exports (Minor, already planned) |
| Follow-up plan review | Review session, 2026-10-08 | Two medium-priority gaps and one import-boundary clarification: exact compatibility oracle, concrete context typing, and direct versus transitive Google imports. Plan amendments applied to activities steps 1/3/6 and exit criteria; implementation gates remain pending. |
| Review-time focused baseline | `.venv/bin/python -m pytest tests/unit/test_google_adapter.py tests/unit/test_google_review_contracts.py tests/unit/test_google_tools_multimodal.py tests/unit/test_google_native.py tests/unit/test_google_lifecycle.py -q` | 168 passed. This regression run does not establish byte-identical behavior; pre-extraction characterization remains pending. |
| Pre-extraction characterization | Baseline runtime `deb05a5`; `tests/fixtures/openai_compatible_characterization.json` | 21 deterministic synthetic scenarios captured before extraction: full rejection/request/response objects, exact SSE bytes, embeddings, parallel calls, schema, refusal, incomplete/missing usage/failure, native ordered output, signed and generated-audio lifecycle. UUID/time/Fernet IV frozen; distinct IDs retained. Oracle must not be regenerated after extraction. |
| Characterization verification | Repository Python 3.14 environment | 189 focused characterization/Google tests passed; final distinct-ID oracle rerun: 21 passed. New test Ruff check/format passed. |
| Implementation | Pending | |
| Verification | Pending | |
| SonarQube / deep review | `scripts/quality/sonarqube-scan.sh`, `.agents/prompts/deep-review.prompt.md` | Absent at plan time |
