# OpenAI-Compatible Adapter Extraction Exit Criteria

## Gate Checklist

- [ ] Plan reviewed by an independent session; findings addressed.
- [ ] `openai_compatible.py` contains no `google_*` imports and no Google feature-profile logic.
- [ ] Every existing test passes unmodified; Google public rejection texts are unchanged.
- [ ] New tests cover fail-closed hooks, label interpolation and a text-only subclass
  (non-streaming and streaming).
- [ ] Full suite passes with ≥ 80% coverage; Ruff check/format and mypy pass.
- [ ] Architecture docs and this plan's evidence updated; relative links resolve.
- [ ] SonarQube script / deep-review prompt run if present (both absent at plan time).

## Approval Table

| Role | Name | Status | Notes |
| --- | --- | --- | --- |
| Owner | Implementing session | Pending | |
| Reviewer | Independent session | Pending | |
| Approver | Maintainer | Pending | |
