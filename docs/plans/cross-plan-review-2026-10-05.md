# Cross-Plan Review — 2026-10-05

## Scope

Independent review of the three plans committed on 2026-10-05, covering commits
`d3a6dec`, `333db5e` and `1c043fd`. Each plan was reviewed by a separate session
against the repository conventions in [AGENTS.md](../../AGENTS.md) and the
planning templates in [docs/templates/](../templates/index.md). Findings were
recorded in each plan's `evidence.md` and consolidated here.

| Plan | Commit | Directory | Verdict |
| --- | --- | --- | --- |
| [Google AI Studio Adapter](../google-ai-studio-adapter/index.md) | `d3a6dec` | `docs/plans/google-ai-studio-adapter/` | Approved — 3 minor findings |
| [Tools and Multimodal](../google-ai-studio-tools-multimodal/index.md) | `333db5e` | `docs/plans/google-ai-studio-tools-multimodal/` | Approved — 2 moderate, 2 minor findings |
| [Model Aliases](../model-aliases/index.md) | `1c043fd` | `docs/plans/model-aliases/` | Approved — 5 minor findings |

## Convention Compliance

All three plans demonstrate full compliance with `AGENTS.md` working rules:

| Convention | Adapter | Tools/Multimodal | Model Aliases |
| --- | :---: | :---: | :---: |
| Status vocabulary (`Planned`, `Implemented`, etc.) | ✅ | ✅ | ✅ |
| Quota vs credit separation | ✅ | ✅ | ✅ |
| Cost values treated as estimates | ✅ | ✅ | ✅ |
| No retry after meaningful streaming output | ✅ | ✅ | ✅ |
| No logging of secrets/prompts/outputs | ✅ | ✅ | ✅ |
| Arbitrary backend counts, no A/B routing | ✅ | ✅ | ✅ |
| 80% coverage + quality tooling gates | ✅ | ✅ | ✅ |
| `maxReplicas: 1` production constraint | ✅ | ✅ | ✅ |

## Template Alignment

All plans meet or exceed the `docs/templates/` structure:

- All six standard templates (`inputs`, `activities`, `outputs`, `exit-criteria`,
  `risk-register`, `evidence`) are instantiated and populated with concrete
  technical detail rather than placeholders.
- Each plan adds a dedicated contract document (`adapter-contract.md`,
  `capability-contract.md` or `alias-contract.md`).
- Common enhancements include partitioned gate checklists (Plan / Code / Live),
  review disposition tables in `evidence.md`, and traceable per-increment scoping.

## Dependency Ordering

The **Adapter** and **Model Aliases** plans are independent and may proceed in
parallel. **Tools and Multimodal** is explicitly blocked on the adapter code gate.

```
Adapter (independent) ──▶ Tools & Multimodal (blocked on adapter)
Model Aliases (independent)
```

## Consolidated Findings

### Google AI Studio Adapter

| # | Finding | Severity | Disposition | Activity |
| --- | --- | --- | --- | --- |
| A-1 | Baseline commit references (`b6a188c`) pre-date two subsequent doc-only commits | Minor | Update during W1 | W1 |
| A-2 | `max_tokens` vs `max_completion_tokens` parameter naming unresolved | Minor | Confirm during vendor contract verification | W1 |
| A-3 | `supported_operations` in `BackendConfig` needs backward-compatible defaults | Minor | Default `["responses", "embeddings"]` for Azure, `["responses"]` for Google | W2 |

### Tools and Multimodal

| # | Finding | Severity | Disposition | Activity |
| --- | --- | --- | --- | --- |
| T-1 | OpenAI SDKs may strip `foundry_provider_state` extension field | Moderate | Test pinned SDK versions in T1; disable capability if stripped | T1 |
| T-2 | `verify_client_auth` lacks principal identifier for continuation binding | Moderate | Add internal caller-scope derivation during T1/T2 | T1/T2 |
| T-3 | `PricingTier` changes must remain backward-compatible with Azure text models | Minor | Ensure additive media pricing dimensions | Inc. B |
| T-4 | Approval table role labels differ from template standard | Minor | Align or note template equivalence | — |

### Model Aliases

| # | Finding | Severity | Disposition | Activity |
| --- | --- | --- | --- | --- |
| M-1 | Runtime 256 KiB alias cap exceeds Azure Container Apps env var limit (~32 KiB) | Minor | Document as defensive runtime bound | A5 |
| M-2 | Routing functions lack `requested_model` / `is_alias` parameters | Minor | Add optional parameters with backward-compatible defaults | A2 |
| M-3 | `/admin/status` placement of `model_aliases` unspecified | Minor | Confirm as top-level key during A3 | A3 |
| M-4 | Startup log omits alias information | Minor | Add to `foundry_router_starting` event | A5 |
| M-5 | Provider response model string returned unchanged to client | Minor | Verify client acceptance in live gates | Live |

## Summary

- **12 total findings** across three plans: 2 moderate, 10 minor.
- **Zero blockers.** All plans are approved for implementation as-is.
- All findings are addressable during their respective implementation activities
  without requiring plan revisions.
- Each plan's `evidence.md` records these findings in its Cross-Plan Review
  Findings section with individual dispositions.
