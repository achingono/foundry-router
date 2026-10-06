# Implementation evidence

**Implemented** for default-off unsigned tools, structured text and small inline PNG.
The parent plan remains **Partially implemented**: signed tools, JPEG/WebP, larger images,
PDFs, additional media, live Google validation and production enablement remain **Planned**.
Native transport progressed separately to [Partially implemented](../native-pdf/evidence.md).

| Item | Evidence | Scope |
| --- | --- | --- |
| Baseline | HEAD `153b1b8`, clean git status | Predecessor already implemented |
| Templates | Seven blank templates copied before authoring | Concrete implementation amendment |
| Official sources | [Contract](contract.md), 2026-10-05 | Public docs fetched; no live inference |
| Sonar script | Absent | Conditional scan unavailable |
| Predecessor regressions | 98 focused tests passed at baseline | Adapter/lifecycle/review-contract/integration |
| Independent plan review | `review_implementation_plan` | Reviewed amendment before runtime edits; strict defaults, token bounds, request context and parser limits addressed |
| Client | OpenAI Python 2.8.1 | Function model_dump/replay and actual ResponseStreamState accumulation; interleaved calls, call-first text, refusals |
| Feature verification | 60 tests | Schema/history/media/combinations/quota, billable conversion failure, env/intake/storage deadlines |
| Full suite | `.venv/bin/python -m pytest tests/unit/ tests/integration/ -m "not docker and not azurite" --cov=src/foundry_router --cov-report=term-missing --cov-report=xml --cov-fail-under=80` | 626 passed, 15 deselected; 87.08% coverage |
| Lint/format/types | `ruff check .`, `ruff format --check .`, `mypy src/` | Passed, 34 source modules |
| Azurite | `test_azurite_distributed_state.py -m azurite` | 14 passed against isolated local emulator |
| Docker | `docker build -t foundry-router:google-tools-multimodal .` | Final build passed; temporary synthetic container `/health/live` returned `{"status":"alive"}`; container removed |
| Final cancellation check | Feature/lifecycle/integration subset after retained-usage alignment | 79 passed |
| Parser measurement | 100 sequential requests, four RGB PNGs each at 384×384 | 58.87 ms total, 0.59 ms/request; tracemalloc Python peak 41459 bytes, excluding native raster memory. No payload cap increase |
| Documentation | 202 changed/new relative links, `git diff --check`, status/secret review | All changed links resolve; claims restricted to code/client scope; historical broken links outside changed files |
| Live Google | Not run; operator model credentials/spend bounds absent | No provider/model or production support claim |

## Independent implementation review

The independent session applied [the deep-review prompt](../../../../.agents/prompts/deep-review.prompt.md)
to the changed owning boundaries/helpers/tests. No Critical findings. Major findings and fixes:

| Finding | Disposition |
| --- | --- |
| Google image ceiling changed Azure admission | Azure legacy path retained; image-enabled pools restricted to Google-only |
| Empty streamed messages/incorrect indices broke replay | Dynamic contiguous public indices, omit nonexistent messages; same-turn call/text reconstruction; actual client-state tests |
| Text parts discarded signatures | Exact content fields/types; signature-bearing outputs fail closed |
| Named choices, malformed names and history ID reuse | Exactly one forced call, bounded string validation and historical ID rejection |
| Historical parallel combination bypass | History independently contributes parallel feature requirements |
| Refusals treated as choice/schema errors | Bounded refusal content/delta/done and distinct validation outcome |
| New-feature text/instructions underreserved | Shared UTF-8 byte ceilings across tools/schema/history/Google images |
| Storage/image intake exceeded time/work bounds | Storage timeout plus cleanup, media aggregate limits before each decode, per-part deadline checks |
| Duplicate outer schema keys collapsed | Bounded outer JSON rejects duplicate keys/nonfinite/deep data |
| Known same-chunk usage lost on conversion/prefetch failures | Normalize independently; retain known settlement through failed/cancelled prefetch; actual HTTP billing regression |
| Documented timeout variable ignored | Explicit FOUNDRY_INTAKE_TIMEOUT_SECONDS alias and env regression |

Final review found no further Critical/Major code/docs findings. Adjacent prefetch cancellation
was aligned with retained usage and rechecked with lifecycle tests. The timeout test now has a
valid backend fixture. Two existing quota doubles now provide valid synthetic input; a stale
Azurite assertion now verifies the existing absolute-deadline keyword as well as backend ID.
