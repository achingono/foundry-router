# OpenAI-Compatible Adapter Extraction Exit Criteria

## Gate Checklist

- [x] Plan reviewed by an independent session; findings addressed.
- [x] `openai_compatible.py` contains no direct runtime Google imports and no Google
  feature-profile logic. Its sole Google import is `PreparedGoogleMedia` under `TYPE_CHECKING`
  for existing protocol annotations; transitive package imports are outside this gate.
- [x] Deterministic characterization fixtures captured and passed before extraction, then
  passed unchanged afterward: complete rejection objects, upstream bodies, translated
  Responses/embeddings bodies and ordered SSE bytes for the cases in activities step 1.
- [x] Read-only shared context protocol and context-parameterized bases preserve concrete
  `GoogleRequestContext` typing, including unchanged native `validate_arguments` calls;
  strict mypy verifies both Google specialization and a Google-independent text-only context.
- [x] Every existing test passes unmodified; Google public rejection texts are unchanged.
- [x] New tests cover fail-closed hooks, label interpolation and a text-only subclass
  (non-streaming and streaming).
- [x] Full suite passes with ≥ 80% coverage; Ruff check/format and mypy pass.
- [x] Architecture docs and this plan's evidence updated; relative links resolve.
- [x] SonarQube script absent; existing deep-review prompt applied and findings addressed.

## Approval Table

| Role | Name | Status | Notes |
| --- | --- | --- | --- |
| Owner | Implementing session | Complete | Local implementation and verification recorded in evidence |
| Reviewer | Antigravity AI | Approved | |
| Approver | Maintainer | Implementation authorized | User requested iterative roadmap implementation; no live enablement claimed |
