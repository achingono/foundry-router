# OpenAI-Compatible Adapter Extraction Evidence

## Status

**Implemented** (2026-10-08), locally verified. No new provider or live enablement.

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
| Implementation | `api/adapters/openai_compatible.py`; thin Google subclasses; package exports | Read-only context protocol, Python 3.12 typed bases, explicit fail-closed provider hooks, preserved Google label and constant aliases. No direct runtime Google imports; sole Google import is the existing media annotation under `TYPE_CHECKING`. |
| Focused verification | Characterization plus Google adapter/review/tools/native/signed/audio/lifecycle suites | 241 passed after extraction; final generic and immutable characterization suite: 30 passed. Existing Google tests and JSON oracle unchanged. |
| Full local verification | `.venv/bin/python -m pytest tests/unit/ tests/integration/ -m "not docker and not azurite" --cov=src/foundry_router --cov-report=term-missing --cov-report=xml --cov-fail-under=80 -q --disable-warnings` | 1,613 passed, 3 platform skips, 15 deselected; 89.18% overall coverage, 87.16% generic module and 100% thin Google module. Final run includes provider-label fixes. |
| Quality/type gates | Ruff check and format for the repository; `mypy src/ tests/typing/openai_compatible_context.py` | Passed. Strict typing proves Google specialization, native argument validation and a minimal text-only context without Google methods. |
| Azurite | Local Table emulator; all 14 marked integration tests | 14 passed with local networking enabled. Initial sandbox run skipped for blocked localhost; skips are not the recorded success evidence. |
| Docker | `docker build -t foundry-router:adapter-extraction .`; network-disabled container smoke | Final image build passed; Python 3.12.15 app liveness, generic/Google imports, nonstreaming response and SSE terminal checks passed. |
| SonarQube | `scripts/quality/sonarqube-scan.sh` | Script absent; no scan claimed. |
| Deep review | [Extraction review](implementation-review.md), following `.agents/prompts/deep-review.prompt.md` | Prompt exists; prior absent-at-plan-time statement corrected. Implementation session completed boundary/lifecycle/security/resource review and addressed label findings. 24 core methods matched original AST after explicit label/constant/type/hook normalization. |

Production remains memory/one. Native/signed/media startup and exact-model live gates are
unchanged. This phase establishes reusable translation code, not Google provider availability
or a configurable generic provider.
