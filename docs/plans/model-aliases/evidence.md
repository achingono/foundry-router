# Model Alias Evidence

## Status

**Planned** implementation. This log records planning only, with no alias rollout or approval-policy change.

## Evidence Log

| Item | Reference | Notes |
| --- | --- | --- |
| Baseline | `333db5e`; `git status --short --branch` | Clean working tree; local main ahead of origin/main by three commits before drafting |
| Reported failure | Retained `git push origin main` escalation result in this session | Approval tool reported HTTP 404 and `Model 'codex-auto-review' not found`; push was not executed. Provider-side logs/body were not independently inspected. |
| User request | Current conversation | General custom/hidden model aliases; also names `codex-auto-approve` and proposes target `gpt-6.1-sol` |
| Target historical inference | [Production evidence](../production-inference/evidence.md) | Normal/streaming `gpt-6.1-sol` inference and usage through fs-swarm recorded; not live availability/reviewer equivalence |
| Source/tests inspected | [Inputs](inputs.md) | Current API accepts canonical pool names only; backend deployment substitution already exists; settlement/pricing use model identity |
| Templates | [Templates](../../templates/index.md) | Copied index and all six companion templates before drafting |
| Concrete plan | [Alias contract](alias-contract.md), [activities](activities.md) | Explicit config, identity boundaries, account inheritance, passthrough, catalog, infra wiring and test gates |
| Independent plan/design review | Separate session `/root/review_model_alias_plan`, 2026-10-05 | Applied deep-review architecture/business/security/resource themes against actual source/tests; no Critical/Major or blocking findings; evidence-attribution suggestion addressed |
| Documentation checks | `.venv/bin/python` relative-link/template/whitespace check; `git diff --check`; content inspection | 94 relative targets across nine touched Markdown files resolve; no template/whitespace issues; final secret/status claims reviewed |
| Sonar script | Absent in inspected tree | Recheck conditionally during implementation |
| Runtime/provider/approval verification | Not run | Documentation-only work; no change to approval review and no retry of the blocked push |
| Cross-plan review | [Consolidated review](../cross-plan-review-2026-10-05.md), 2026-10-05 | Reviewed alongside adapter and tools/multimodal plans; 5 minor findings recorded; plan approved for implementation |

## Review Dispositions

| Finding | Severity | Disposition |
| --- | --- | --- |
| Escalation error wording could imply an independently confirmed provider root cause | Suggestion | Quote/attribute the retained tool's reported HTTP404/model name and state provider logs/body were not independently inspected. |

The reviewer confirmed no blocking design findings. This is a plan review, not implementation,
current target availability or actual approval-client validation.

## Cross-Plan Review Findings

Independent cross-plan review session, 2026-10-05. Reviewed alongside
`google-ai-studio-adapter` and `google-ai-studio-tools-multimodal` plans.

| Finding | Severity | Disposition |
| --- | --- | --- |
| `FOUNDRY_MODEL_ALIASES_JSON` runtime parser caps at 256 KiB but Azure Container Apps env vars are practically bounded to ~32 KiB | Minor | Document that the runtime bound is defensive; container environment configuration in Bicep is practically limited by Azure Container Apps environment limits |
| `execute_with_single_failover` / `select_candidate_backend` do not accept `requested_model` or `is_alias` parameters | Minor | During A2, update routing signatures to accept optional `requested_model` / `is_alias` (or an immutable `ModelIdentityContext`) defaulting to direct-model behavior for backward compatibility |
| `/admin/status` schema placement of `model_aliases` is unspecified (top-level vs nested under `config`) | Minor | Confirm during A3 that `model_aliases` is a top-level key alongside `models` for consistent admin tooling discovery |
| `foundry_router_starting` log event in `main.py` does not include alias information | Minor | Add `model_aliases=list(settings.model_aliases.keys())` (or alias count) to the startup event during A5 so operators can verify active aliases on container start |
| Provider response `model` string (e.g. `gpt-6.1-sol-2024-08-06`) is returned unchanged; client must accept it | Minor | Plan correctly mandates no SSE rewriting (R7); verify client acceptance during Separate Live Gates |

Verdict: **Approved for implementation** with no blocking findings. All five items are
minor and addressable during their respective implementation activities (A2–A5 and
live gates) without plan revision.

## Future Evidence

Record actual unit/integration/coverage/lint/type/Docker/Bicep/CI and implementation review results.
Keep live route success and actual reviewer-contract verification separate; retain no sensitive
reviewer context, prompt/output bodies or credentials. User-provided references are background,
not verified Codex configuration documentation.
