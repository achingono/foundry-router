# Independent Zen/OpenRouter plan review

Date: 2026-10-09.

Scope: the seven original plan documents, checked against canonical API,
configuration, security and routing documentation, current configuration/backend
client code, adapter selection and validation, forwarding/settlement paths, and
existing compatible-provider unit/integration tests.

The reviewing assistant performed the initial independent review in this session
at the user's request, before editing the plan. The user subsequently requested
the revisions and this record. Finding disposition below was checked by the same
reviewer; this is not a claim of another independent model or second review session.

## Initial findings

### PR-1 — Major: Zen lifecycle reuse conflicts with accounting requirements

- **Location:** [Activities, steps 3 and 6](activities.md), compared with
  [contract item 5](index.md).
- **Issue:** The original activities directed reuse of Azure pass-through
  forwarding while explicitly assigning single-shot execution and conservative
  settlement to OpenRouter. The contract required those guarantees for both.
  Existing Azure forwarding retries transport failures and selected 5xx statuses,
  permits routing failover, and does not use the translated path's explicit
  billable-failure settlement results.
- **Impact:** Direct reuse could repeat a billable Zen generation or refund an
  ambiguous dispatched attempt. Merely preserving SSE bytes does not preserve
  the intended attempt/accounting policy.
- **Required correction:** Separate wire pass-through from execution policy;
  specify Zen's single-shot dispatch, 429-only failover, auth cooldown and
  cancellation/ambiguous-failure settlement for streaming and non-streaming.
  Require retry-count, charge and cleanup assertions with `retry_attempts > 1`,
  preserving existing Azure behavior.
- **Disposition:** Addressed in the revised contract, activities, exit criteria
  and risk R9. Dispatch/usage facts, pre-dispatch release, conservative dispatched
  settlement and ownership cleanup are explicit. Implementation remains Planned.

### PR-2 — Major: Zen pre-admission rejection lacks an enforcement mechanism

- **Location:** [Contract item 3](index.md) and [activities, step 5](activities.md).
- **Issue:** The original plan promised rejection of non-Responses wires and
  restricted support to Zen's Responses model rows, but accepted any bounded
  single-segment deployment and allowed Azure-equivalent adapter behavior.
  Azure's request check accepts every body; public intake does not enforce a
  Responses field allow-list. Neither boundary established the promised gate.
- **Impact:** Foreign fields could survive intake, or an incompatible configured
  model could reach the upstream after quota/credit admission despite the stated
  local rejection guarantee.
- **Required correction:** Define Zen request validation and zero-admission
  negative tests. Establish a model capability mechanism or explicitly make
  upstream model selection an operator responsibility and narrow the guarantee.
- **Disposition:** Addressed in the revised contract, activities, exit criteria
  and risk R10. Initial Zen requests use an explicit bounded stateless-text
  allow-list; accepted bodies retain their Responses wire form. Unsupported and
  foreign fields are rejected for the Zen candidate before admission, including
  when paired with otherwise valid input. Mixed pools retain other capable
  candidates. Broader tools/media/continuation support is deferred. Operators
  select a Responses-compatible model; the router makes no catalog-validation
  or local rejection guarantee for misconfigured model families.

These are contextual contract/architecture findings, not static-analysis
findings. No SonarQube scan or implementation deep review was performed here.

## Revised-plan disposition

Both Major findings are addressed at the planning level. The revised plan is
cleared for implementation; no unresolved Critical or Major plan findings remain
from this review. This clearance does not establish runtime correctness, upstream
compatibility or production readiness. Risks R9/R10 remain open until their
implementation/live verification gates are met.

## Verification scope

- Initial review: all 15 relative Markdown links resolved; staged whitespace
  checks passed.
- Revision: relative links across all eight plan documents and staged/unstaged
  whitespace checks passed; final diff reviewed for scope and unsupported claims.
- No runtime code, tests, infrastructure or production configuration changed.
- Runtime tests, coverage, lint/type checks, Docker build and live-provider
  verification were not run for this documentation-only revision. Their
  implementation gates remain unchecked in [exit criteria](exit-criteria.md).
