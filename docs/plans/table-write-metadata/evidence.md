# Table write metadata evidence

Historical logs on 2026-10-09: routing selected at 10:55:17 UTC followed by
TableTransactionError HTTP 400 at 10:55:19 UTC. Later read-only status confirmed
zero active reservations/inflight and remaining estimate 99.96919 for model-1;
the reaper conservatively debited the 0.03081 USD reservation estimate. Exact
provider response and Azure error text are not known.

Independent plan and contextual implementation reviews cleared Critical/Major findings.
Exact transport-key sanitation preserves application metadata, input mappings and ETag guards.
Real SDK recorded multipart bytes verify If-Match and metadata-free settlement body.
Strict cloud property-name checks around real Azurite finalize/reap passed.

- Focused: 34 passed; Azurite baseline: 17 passed before the new strict case.
- Full: 2,052 passed, 3 skipped, 19 deselected; coverage 89.86%.
- Ruff, formatting and strict mypy passed. SonarQube script absent.
- amd64 Docker build and network-disabled runtime imports passed.
- Image (local-only `image-result.json`): all platform manifest/config/layer hashes verified.

Cloud probe (local-only `cloud-probe-result.json`) could not start: Container Apps exec WebSocket
returned 404, including with the exact ready revision/replica/container and a shorter
command. No result marker was returned. Private durable synthetic ownership is retained;
no unowned rows or real model balances are modified. No provider calls were made.
This is an exec transport failure, not evidence of cloud write acceptance.
The code defect is corrected locally; exact cloud root cause and live inference remain open.

## Supplemental execution amendment

Independent review cleared the concrete image-only update and two previously unattempted
streaming cases under the original four-call/0.15 USD limits, after zero-active confirmation.
The supplemental runner holds both ledger locks and preserves the original bytes/budget.
Review caught the original stage validator requiring passing nonstream predecessors; an
explicit strict supplemental result validator corrected this before traffic. Synthetic two-pass,
first/second-failure stop, observation persistence and replay refusal checks passed.
See runner checks (local-only `supplemental-runner-result.json`), the exact reviewed
runner source (local-only `supplemental-runner.txt`) and synthetic check source (local-only `supplemental-runner-checks.txt`).

## Corrected isolated deployment and live streaming

The verified corrected image was pushed and only the existing isolated app image changed.
Azure CLI temporarily normalized secretRef-only environment entries with empty values;
binding rejected the response. A scoped ARM template patch restored exact configuration
equivalence before provider traffic. Deployment binding (local-only `deployment-result.json`) passed.

Both previously unattempted supplemental streaming cases (local-only `supplemental-ledger.json`) passed:
HTTP 200, terminal completed/text flags, verified usage, matching local estimated debit and
zero active/inflight reservations. Model-1: 12 input/22 output tokens, 0.00078 USD estimated
debit. Model-2: 12 input/30 output tokens, 0.00102 USD estimated debit.
Post-run status (local-only `post-supplemental-status.json`) confirms both cleared.

The original ledger SHA-256 remains unchanged. Both old entries consume request/reservation
budget; total maximum four cases reserve 0.12544 USD under the original 0.15 USD limit.
No remaining router requests are available in that authorization. No Google calls, production
changes, manual balance reset or restart occurred. Original nonstream acceptance and restart
remain open; supplemental evidence establishes streaming settlement on the corrected cloud
image and does not rewrite the failed history or prove the exact old Azure error text.
