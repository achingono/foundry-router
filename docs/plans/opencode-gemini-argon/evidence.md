# Evidence

Status: **Implemented with mocked verification; live inference and deployment Planned**.
October 13, 2026 (America/Toronto).

| Check | Result |
| --- | --- |
| Initial tree | Clean git status; canonical docs/current tests inspected before edits |
| Vendor discovery | Public OpenCode legacy/current catalogs HTTP 200 list exact `gemini-4-argon`; current model table specifies native Google route; Google exact model guide documents low/medium/high thinking |
| Current production | Azure read-only query: Succeeded; ready revision `foundry-router-production--or-two-20261012`; max one replica; image matches last recorded release |
| Independent plan review | [Review](review.md): implementation approved, no Critical/Major findings |
| New provider tests | 55 passed: strict profile/raw-root/model segment safety, native URL/Bearer/body, alias/SSE, thought-inclusive settlement, zero-egress unsupported requests, single-shot 401/403/429/5xx, freshly admitted 429 failover, no partial-stream failover |
| Focused native regressions | 108 passed (new tests plus existing native adapter/thinking/HTTP integration) |
| Full suite | 2,586 passed, 3 skipped, 19 deselected (`not docker and not azurite`); runtime coverage 90.12% (>=80%) |
| Lint/format/types | Ruff src/tests clean; all 204 Python files formatted; strict mypy 72 source files clean |
| Docker build | Final `foundry-router:opencode-argon` build passed after final URL consolidation; native startup smoke recorded separately below |
| Azurite | 18 tests skipped because local Table emulator was unavailable; no Table behavior changed or Table deployment claim made |
| Conditional Sonar | `scripts/quality/sonarqube-scan.sh` absent |
| Contextual review | [Implementation review](implementation-review.md), final verdict recorded there |
| Packet | [Configuration delta](configuration-delta.json), [acceptance manifest](acceptance-manifest.json), [deployment packet](deployment-packet.md): Planned; exact files allow-listed in .gitignore |
| Links/diff | All checked relative targets resolve; JSON packet syntax valid; git diff --check clean |

The initial sandbox full run could not bind existing loopback listeners and was
stopped. Its replacement ran with loopback access and fully passed. The measured
Azurite marked check skipped without an emulator. Existing Python 3.14
deprecation warnings remain.

No inference, credential output, vault write/grant, remote image push, staging
restart or production mutation occurred. Existing Azure production settings,
writer and authentication are preserved. Maintenance/account inputs, a reviewed
durable runner, exact immutable Linux/config bindings, bounded live staging and
production acceptance and fresh all-account credit handoff remain Planned.
Catalog presence and mocked tests establish neither live model/account
availability nor production inference.

Final container smoke passed with network disabled: native OpenCode configuration startup, liveness, readiness and authenticated model discovery. No upstream dispatch occurred.
