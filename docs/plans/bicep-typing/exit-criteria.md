# Bicep Typing Exit Criteria

## Gate Checklist
- [x] Independent plan review approved.
- [x] Shared types consumed by the root and existing modules.
- [x] Invalid literals and misspelled fixed config properties fail compilation.
- [x] Public parameter names/defaults and output names/types remain compatible.
- [x] Resource identity, scopes, credentials, replica guard and state endpoint semantics preserved.
- [x] Positive/negative Azure validation and reviewed what-if pass; synthetic memory smoke checks pass.
- [x] Full suite at least 80% coverage, lint/format/type checks and Docker build pass.
- [x] Deep review, documentation and link validation complete.

## Approval Table

| Role | Name | Status | Notes |
|---|---|---|---|
| Owner | Coding session | Complete | Typing foundation deployed and verified |
| Reviewer | Independent session | Approved | Plan and semantic ARM deep review |
