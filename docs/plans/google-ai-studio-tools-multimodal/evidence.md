# Tools and Multimodal Evidence

## Status

**Planned**. Drafting and review evidence only. No runtime implementation, current vendor
verification, media inference, tool round trip or production enablement is established here.

## Evidence Log

| Item | Reference | Notes |
| --- | --- | --- |
| Predecessor committed | `d3a6dec` — `docs: plan Google AI Studio backend adapter` | Nine documentation files committed on 2026-10-05; no runtime implementation in that commit |
| Draft baseline | `git status --short` after predecessor commit | Clean tree before this follow-up draft |
| Current contracts inspected | [Inputs](inputs.md) | Canonical docs, source, tests, predecessor and templates inspected |
| Concrete gaps | `BackendConfig`, `request_body`, `estimate_request_cost`, provider client and test search | No feature profiles, tool/signature/media adapters or modality-aware estimates; predecessor interfaces are still Planned |
| Templates | [Planning templates](../../templates/index.md) | Index plus six companion templates copied into the follow-up directory before authoring |
| Draft outputs | [Index](index.md), [capability contract](capability-contract.md), [activities](activities.md) | Per-increment scope, mappings, dependencies, accounting/resource/security gates and tests |
| Independent plan/deep design review | Separate session `/root/review_tools_multimodal_plan`, 2026-10-05 | Applied architectural, business-logic, trust-boundary and resource-economic themes; one Major finding and one Suggestion addressed; follow-up review confirmed no blocking findings |
| Documentation checks | `.venv/bin/python` relative-link/whitespace/template check; `git diff --check`; content inspection | 91 relative targets across nine touched Markdown files resolve; no template/whitespace issues; diff and secret/status claims reviewed |
| SonarQube script | Absent at inspected baseline | No scan performed; conditional implementation gate retained |
| Runtime/provider checks | Not run for this documentation-only task | No code tests, live calls, media/tool execution or deployed-capability claims |
| Cross-plan review | [Consolidated review](../cross-plan-review-2026-10-05.md), 2026-10-05 | Reviewed alongside adapter and model-aliases plans; 2 moderate + 2 minor findings recorded; plan approved for implementation |

## Review Dispositions

| Finding | Severity | Disposition |
| --- | --- | --- |
| A stripped continuation carrier could escape through a healthy unsigned backend in a mixed pool | Major | Pool-wide `bound_history_required` validation precedes candidate filtering; incomplete/missing state fails before admission/egress even with healthy Google/Azure alternatives; unsigned tool workflows use separate pools. |
| Reservation deadline wording could leave pre-admission validation timing ambiguous | Suggestion | Intake deadline/work budget bounds schema/media/state checks before reservation; remaining intake lifetime and initial reservation deadline both apply afterward without reset. |

The independent session re-read the changed contract, activities, exit criteria and risks and
confirmed both findings closed, with no Critical/Major findings remaining. It also confirmed
that deferred native/media schemas and per-capability gates do not establish implementation.
These are plan-review conclusions, not runtime/client/vendor verification.

## Cross-Plan Review Findings

Independent cross-plan review session, 2026-10-05. Reviewed alongside
`google-ai-studio-adapter` and `model-aliases` plans.

| Finding | Severity | Disposition |
| --- | --- | --- |
| Official OpenAI Python/Node SDKs with `extra="forbid"` Pydantic models may strip or reject the `foundry_provider_state` extension field on deserialization | Moderate | Plan anticipates this in T1 and R2; during T1 explicitly test pinned SDK versions for field preservation and document client requirements or restrictions if stripped |
| Auth layer (`verify_client_auth`) returns raw keys without a principal identifier; continuation token binding needs a stable caller scope | Moderate | Plan accurately identifies the gap; document the caller-scope generation function (e.g. `HMAC_SHA256(matched_key, salt)`) during T1/T2 as a non-breaking internal enhancement to `verify_client_auth` |
| Increment B changes to `PricingTier` / `estimate_request_cost` must remain backward-compatible with existing Azure text models and `test_credit.py` | Minor | Ensure media pricing dimensions are additive; existing text-only pricing paths and test assertions must continue to pass without modification |
| Approval table role labels (`Draft author`, `Independent reviewer`, `API/release approver`) differ from template standard (`Owner`, `Reviewer`, `Approver`) | Minor | Functionally equivalent; align or parenthetically note template labels for strict conformity |

Verdict: **Approved for implementation** with no blocking findings. The two moderate items
are addressable during T1/T2 without plan revision; both are already anticipated by
existing plan activities and risks.

## Future Evidence

Record T1 source dates and decisions, actual predecessor code-gate reference, per-increment
test/coverage/lint/type/Azurite/Docker results and independent code reviews. Record pinned-client
signature/tool replay separately from actual provider results. Keep live evidence to test case IDs,
versions, result assertions and usage/redacted diagnostics; never retain keys, signature envelopes,
prompts, arguments/results, generated content or media payloads. Synthetic fixtures are separate.
