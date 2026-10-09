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
- [Image](image-result.json): all platform manifest/config/layer hashes verified.

[Cloud probe](cloud-probe-result.json) could not start: Container Apps exec WebSocket
returned 404, including with the exact ready revision/replica/container and a shorter
command. No result marker was returned. Private durable synthetic ownership is retained;
no unowned rows or real model balances are modified. No provider calls were made.
This is an exec transport failure, not evidence of cloud write acceptance.
The code defect is corrected locally; exact cloud root cause and live inference remain open.
