# Tools and Multimodal Evidence

## Status

**Partially implemented**. Historical draft evidence below predates the implemented predecessor.
Current code, client, review and verification evidence is in the
[implementation amendment](implementation/evidence.md). No live Google or production claim.

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

## Implementation progress

The full plan remains **Partially implemented**; see [completion audit](completion-audit.md).
[Native/PDF evidence](native-pdf/evidence.md) now records local PDF gate completion: independent
review,801 full local tests/87.95% coverage,92 actual Linux PDF tests, and current full-path
8×100 mixed/aggregate/late-invalid resource measurements. No live Google calls or production
enablement. [Signed continuation design](signed-continuation/design.md) is under independent
review; signed runtime and remaining media directions remain required.

2026-10-06 continuation: [Finite WAV](audio-input/evidence.md) and
[raw DIB AVI](video-input/evidence.md) are partially implemented with independently reviewed
bounded input parsers, native mapping, MIME-specific estimates, actual SDK fixtures and Linux
measurements. Combined/state/live gates remain open. Five authorized model-list GETs discovered
61models/project; no inference. [Dormant live runner](live-runner/evidence.md) owns budget and
isolated synthetic runtime; all-model manifest has zero approved dispatch cases.

Latest local checkpoint:1203passed,2Linux-onlyskips,15Docker/Azuritedeselected,89.05%coverage;
Ruff/format/mypy, Python3.12Dockerbuild/health and184relative links pass. Sonarscriptabsent.
Signed startupgate unchanged; generatedimage/audio,largerimage and all exactmodellive gates
remain incomplete. Production unchanged. Do not mark the full objective complete.

2026-10-06 generated-audio continuation: gated integration, SDK/lifecycle/input-quota tests
and exact maximum/malformed Linux WAV measurements added. Local checkpoint1404passed,89.17%;
Ruff/format/mypy pass. Corrected mixed Linux resource and final independent review remain
pending after external approval/reviewer service503; no command bypass. See
[scoped evidence](generated-audio/evidence.md). Full plan remains partially implemented;
startup gates and production configuration unchanged. No new provider inference requests.

2026-10-06 continuation closes local generated-audio mixed-resource/deepreview and actualsigned
fresh-process replay gates. Final full1409passed/89.17%, Ruff518/mypy61 and100relative links pass.
Corrected mixedWAV/PNG78,069,760B aggregateRSS with4WAV/34PNG, zero activecredit/quota rows;
independentreviewclear. Signed local3.14/Linux3.12 sequentialSDK replay and changedkey422 pass;
boundedpipeoverflow/cancel regressions and deepreviewclear. Evidence is syntheticonly; container/
TCPrestart, combinedmaxstate/media and all exact-model live requirements remain open. See
[process evidence](signed-continuation/evidence.md) and
[audio output evidence](generated-audio/evidence.md). Startup gates remain closed, no live
inference or production/config changes. Next [combined-resource amendment](signed-continuation/combined-resource-design.md)
is submitted for independent preimplementation review.

2026-10-06 quotedmaximum continuation: validated125historyitem/exactcontext fixture and actualSDK
streamcompletion/newcarrier/headroom/wire checks implemented. FullLinux8×100completed26valid/
774busy,correctbilling/cleanup, but failed152846336BRSS/158.35msloop. Independentlyreviewedhybrid
JSONscanner optimization passes167focused/39531differential,full1422/89.18%,Ruff522/mypy61,
Dockerbuild/health27.92sec. Onecaller43.31msloop passesbutdoesnotreplacefailedconcurrentgate.
Next [verification-only attribution](signed-continuation/resource-attribution-design.md) approved;
startup/live/production unchanged. Remaining parentrequirements preserved in completionaudit.
