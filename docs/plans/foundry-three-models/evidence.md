# Foundry three-model evidence

Status: Implemented and deployed; live acceptance passed, public intake restored. See [production evidence](production-evidence.md).

- Previous accounting correction committed as 3c9623e; unrelated Responses request-limit plan remains untouched.
- Azure inventories verified gpt-6.1-terra and MAI-Image-2.6 in both accounts, and claude-sonnet-5-5 in openclaw. User chose MAI through Responses image output.
- [Independent plan review](plan-review.md) approved generic implementation before edits.
- Dedicated providers reuse the existing nonstream text/PNG transport and ownership boundaries; Google output startup gating and the strict PNG inspector remain unchanged.
- 45 new focused regressions passed, covering configuration/auth/routes, logical/physical identity, image projection without invented usage, actual API ledger charging and exactly-once lease cleanup, malformed output, cancellation and confirmed pre-dispatch release. Existing 123 Anthropic/backend/accounting regressions passed before new cases.
- Full suite passed: 2,850 tests, 3 skipped, 19 deselected, 90.42% coverage. Ruff/format and mypy (76 sources) passed. Final Linux/amd64 Docker health and isolated PNG worker verification passed. [Independent verification](verification.md) and [implementation review](implementation-review.md) approved the implementation. ACR run ca9 succeeded with the immutable digest in the [production packet](production-packet.md); initial release executed; MAI compatibility was corrected in the verified replacement release.
- SonarQube script is absent: N/A, not a scan pass. Linux PNG compatibility was a separate enablement gate and passed for the exact live MAI output in the replacement release.

- [Pricing evidence](pricing-evidence.md) establishes Terra Standard Global meters; maximum input including cache-write is USD 2.50/M, maximum cached input USD 0.10/M and output USD 7.50/M. No Priority meter is published.
- User explicitly approved Sonnet local estimates USD 4/M input / USD 10/M output and MAI USD 1 per bounded image request. These are operator routing estimates, not verified Azure prices or guarantees of a billing ceiling. They are deployed local estimates; preserve that distinction in billing claims.

Public GET /openai/v1/models returned HTTP200 with all three requested model IDs after restoration; readiness remained HTTP200/ready=true. Independent [final review](final-review.md) confirmed accounting and deployment claims.
