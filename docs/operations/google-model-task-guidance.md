# Google model task guidance

**Design target** for workload selection; source review dated **2026-10-08**. This guide preserves candidate tasks suggested by published benchmarks, model guides and public discussion. Task-quality evaluation in Foundry Router remains **Planned**; local text transport and quota observations are recorded in the [capacity inventory](../plans/google-ai-studio-capacity-inventory/index.md) and [current observations](../plans/google-ai-studio-capacity-inventory/current-observations.md).

Use **3.6 Flash for bounded coding and document analysis**, accessible **Flash-Lite for straightforward extraction and translation**, and **Robotics ER for spatial interpretation** when its required capabilities are validated. Published strengths do not establish current availability or production readiness. In particular, 3.5 Flash-Lite failed the latest probes despite earlier success.

## Candidate task mapping

| Exact model | Candidate tasks | Evidence and operational limits |
| --- | --- | --- |
| `gemini-3.6-flash` | Bug fixes, code migrations, test generation, document comparison, chart analysis, report drafting | Google reports coding, computer-use and professional-work benchmark improvements over 3.5 Flash [S1]. These motivate evaluation, not a task-quality guarantee. Small local text probes completed across five projects; availability failures also occurred. |
| `gemini-3.5-flash` | Bounded coding assignments, frontend prototypes, decomposing work into steps, document/image interpretation | Google emphasizes agent workflows [S2]. Public reports praise speed and vision but disagree on autonomous coding and instruction following [S7–S8]. Local availability was intermittent during paced probes. |
| `gemini-3-flash-preview` | Screenshot-assisted coding, UI prototypes, multimodal questions, reasoning with supplied context | Google emphasizes multimodal understanding and coding [S3]. Local small-text bursts reached explicit quota rejection on all five projects. The provider uses quota model dimension `gemini-3-flash`; do not count aliases as separate capacity. |
| `gemini-2.5-flash` | Summarization, document questions, moderately complex extraction, bounded reasoning | General-purpose task candidate from Google's positioning [S4]. Projects 1–2 completed local text probes; projects 3–5 returned 404. Local tests used thinking budget zero, so they do not establish thinking-enabled reasoning performance. |
| `gemini-2.5-flash-lite` | Classification, entity extraction, translation, tagging, straightforward text transformations | Google explicitly recommends lightweight classification and extraction [S4]. Available on projects 1–2 in local tests; 20 RPD was explicitly observed there. |
| `gemini-3.1-flash-lite` | Translation, document triage, simple extraction, classification | Google provides these concrete use cases [S5]. Initial local probes completed everywhere; subsequent project ramps all stopped on timeouts. Keep conditional on a fresh availability check. |
| `gemini-3.5-flash-lite` | Extraction plus lightweight coding, alternative designs, receipt translation and summarization | Google reports substantial gains over earlier Lite models [S1]. Latest local probes failed on every project; defer normal traffic until recovery is demonstrated. |
| `gemini-3.8-flash` | Complex debugging, longer software-engineering assignments, coordinated business workflows | These are Google's advertised targets [S6]. Fewer independently corroborated task results were verified in this review; local availability and streaming were inconsistent. |
| `gemini-robotics-er-2-preview` | Object localization, instrument reading, physical-scene interpretation, video progress checks, physical task planning | Google's specialist embodied-reasoning guide supports these candidates [S9]. Local text responses do not validate visual/spatial capabilities or physical execution. Use the exact endpoint; the separate streaming endpoint was not validated. |
| `gemma-4-26b-a4b-it`, `gemma-4-31b-it` | Experimental secondary opinions or bounded extraction | No supported specialist assignment emerged from this source review. Local provider errors and timeouts also weaken their suitability as defaults. |

No specialist task ranking is established here for `gemini-3.7-flash`; local availability was inconsistent. Other discovered models lack affirmative free-tier task/capability evidence in this review. Catalog presence alone does not authorize dispatch.

## Benchmark evidence and its limits

Google's 3.6 Flash launch report [S1] compares it with 3.5 Flash:

| Evaluation | 3.6 Flash | 3.5 Flash | Candidate work it helps motivate |
| --- | --- | --- | --- |
| DeepSWE | 49% | 37% | Software repair and modification |
| MLE Bench | 63.9% | 49.7% | Machine-learning engineering experiments |
| OSWorld-Verified | 83.0% | 78.4% | Computer interaction |
| GDPval-AA v2 | 1421 | 1349 | Professional documents and knowledge work |

These are **vendor-reported results**, not benchmarks reproduced by this repository. Agent harnesses, tool access, thinking levels and output budgets affect results; benchmark scores cannot be transferred directly to our tested text profiles. The same report describes 3.5 Flash-Lite improvements in coding and agent workflows, which remain candidate strengths despite its current local availability failures.

Artificial Analysis independently characterizes the **high-thinking** 3.6 Flash variant as notably fast with above-average intelligence among comparable models [S10]. Its page has historical workload/deprecation caveats; that label does not prove shutdown of the Gemini Developer API endpoint. This guide makes no latest-rank or pricing claim. Different benchmark versions and thinking profiles should not be compared as identical measurements.

## What public discussion adds

Zvi's 3.5 Flash review [S7] collects positive reports about handwriting, table rows/columns, reading dials, spatial awareness and fast coding, alongside weaker third-party coding results and instruction-following complaints. These are attributed reports, not independently verified task comparisons.

The Hacker News discussion [S8] includes reports of strong bounded coding/tool tests that did not translate into dependable autonomous repository modification. Other commenters describe useful screenshot, chart and image inputs while coding. The discussion is a selected anecdotal sample, not consensus or a controlled comparison.

This supports an initial preference for **well-scoped work with verifiable outputs**: a specific patch, document comparison, extracted record or translation. It does not establish reliable unattended agents, factual accuracy, or good grading/judgment merely from coding benchmark performance.

## Use the scarce daily allowance

The inventory records 20 RPD for 19 model/project buckets; five other buckets have measured RPM/input TPM but unknown RPD. Treat these as dated per-bucket observations, not guaranteed aggregate throughput. Multiple keys from one project and model aliases do not create allowances; additional shared limits remain unverified.

Candidate allocation:

- **3.6 Flash:** one substantial code review, migration analysis or document synthesis per request, using relevant context and explicit acceptance criteria.
- **3 Flash Preview / 3.5 Flash:** independent second opinions and screenshot-assisted debugging once the media path is validated.
- **Accessible Flash-Lite:** bundle related extraction, tagging or translation items into a bounded request with separate result IDs. Avoid spending a scarce request on model selection when ordinary rules suffice.
- **Robotics ER:** reserve for spatial/image tasks after exact-model input and output validation, rather than treating working text probes as proof of a specialist use case.

Cache reusable results, deduplicate before dispatch, prioritize valuable work and queue optional tasks after daily exhaustion. Respect measured RPM/input TPM, cooldowns and conservative dispatch accounting. A large context window does not imply that an equally large prompt fits the per-minute allowance. Provide enough output budget for a useful answer; thinking and tools can consume additional tokens and requests. Never retry after meaningful streaming output begins.

Text-only document analysis can use extracted text within existing bounds. Native images, PDFs, audio/video, structured outputs, tools and signed continuation retain their separate [feature operations](google-features.md) and [implementation/live gates](../plans/google-ai-studio-tools-multimodal/completion-audit.md). Some recommended tasks require those gates before they can run through the router. Production remains memory-backed with `maxReplicas: 1`; this guide changes no configuration or enablement.

Before promoting a candidate, compare representative workloads by accepted-result rate, factual/extraction accuracy, substantive code checks, latency, token use and provider failures. Refresh the recommendations when model versions, quotas, availability, thinking profiles or benchmark methodology change. Recheck current provider documentation before implementing a capability.

## Sources

Sources were read on 2026-10-08. Their contents and model lifecycle statements may change.

- **S1 — Vendor report:** [3.6 Flash and 3.5 Flash-Lite launch](https://blog.google/innovation-and-ai/models-and-research/gemini-models/gemini-3-6-flash-3-5-flash-lite-3-5-flash-cyber/).
- **S2 — Model guide:** [3.5 Flash](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash).
- **S3 — Model guide:** [3 Flash Preview](https://ai.google.dev/gemini-api/docs/models/gemini-3-flash-preview).
- **S4 — Model guides:** [2.5 Flash](https://ai.google.dev/gemini-api/docs/models/gemini-2.5-flash) and [2.5 Flash-Lite](https://ai.google.dev/gemini-api/docs/models/gemini-2.5-flash-lite).
- **S5 — Model/developer guide:** [3.1 Flash-Lite](https://ai.google.dev/gemini-api/docs/models/gemini-3.1-flash-lite).
- **S6 — Model guide:** [3.8 Flash](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash).
- **S7 — Commentary and collected anecdotes:** [Zvi's 3.5 Flash review](https://thezvi.wordpress.com/2026/05/22/gemini-3-5-flash-looks-good-for-how-fast-it-is/).
- **S8 — Public discussion:** [Hacker News 3.6 Flash launch thread](https://news.ycombinator.com/item?id=48993414).
- **S9 — Specialist model guide:** [Robotics ER overview](https://ai.google.dev/gemini-api/docs/robotics-overview).
- **S10 — Independent evaluation:** [Artificial Analysis 3.6 Flash, high-thinking](https://artificialanalysis.ai/models/gemini-3-6-flash).
