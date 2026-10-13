# Two-model OpenRouter production deployment

Status: **Implemented and deployed; both non-streaming production acceptance checks passed**.
Final verification: October 13, 2026 (America/Toronto). The operator authorized production deployment and confirmed closed intake, account allocations, provider terms and monitoring ownership.

## Release and topology

Candidate image: `grimsugar.azurecr.io/foundry-router@sha256:ee24fc37d9198a7824937339337468a355b937a57b53c03d79b05138355c8b57`.
ACR build `ca1` succeeded. Production revision: `foundry-router-production--or-two-20261012`.
The six existing pools, twelve Azure backends and aliases were preserved. Two OpenRouter backends and pools were added:

| Model | Deployment | Mode |
| --- | --- | --- |
| `gpt-6-luna-or` | `openai/gpt-6-luna` | Non-streaming Responses |
| `claude-haiku-5.5-or` | `anthropic/claude-haiku-5.5` | Non-streaming Responses |

Both pools set strict `streaming_enabled: false`. The API rejects `stream: true` before provider preparation or credit/quota admission, including aliases. A mixed-pool regression confirms that other enabled pools still stream. Admin diagnostics report the effective policy. This release adds no Zen, DeepSeek, MiMo or Spark production entries.

Existing identity, environment, ingress, authentication, Azure pricing, weights and aliases were retained. Production uses memory state, one worker and a maximum of one replica. The pull registry moved to the existing grimsugar registry because the original subscription is disabled. The narrowly scoped runtime AcrPull assignment was recorded and retained for production. All eight secret references explicitly pin coherent versions; authentication was not rotated. Actual secret mappings and values remain private.

## Credit and handoff

The operator supplied fresh conservative values: fs-openclaw disabled, fs-swarm USD 130.66, OpenRouter USD 4.83 and OpenCode USD 10. OpenCode was not added. The disabled account's allowance and remaining credit were set to zero to prevent cycle resets replenishing it; backend memberships were preserved. fs-swarm retains its USD 210 allowance and cycle day 2, with a USD 130.66 seed. OpenRouter uses a USD 4.83 allowance and cycle day 1, with a staging seed of USD 4.82 followed by a production seed of USD 4.81 after bounded staging checks. Global reserves remain USD 10 / 5%; OpenRouter overrides them with USD 0.05 / 5%. Local credit estimates are not authoritative provider balances.

Both apps were confirmed quiet before stopping their writers. After both staging checks passed, a fresh quietness read preceded deactivation of all staging revisions. Zero active revisions and replicas were verified before production started. Staging remains stopped to prevent duplicate OpenRouter allocations. The previous production writer was also confirmed stopped before rollout. The temporary staging vault grant was scoped to that vault, removed and verified absent.

The first staging operational attempt stopped before mutation at a five-second admin read. An independently reviewed amendment permitted a bounded thirty-second operational read and one repeat, which succeeded. Inference bounds and the prohibition on replay were unchanged.

## Acceptance

| Environment/case | HTTP | Input/output tokens | Local debit USD | Settlement/cleanup |
| --- | --- | --- | --- | --- |
| Staging Luna | 200 | 12/5 | 0.0000037 | Passed |
| Staging Haiku | 200 | 17/5 | 0.0000042 | Passed |
| Production Luna | 200 | 12/5 | 0.0000037 | Passed |
| Production Haiku | 200 | 17/5 | 0.0000042 | Passed |

All four immutable ledger slots were consumed and cannot replay. Their local debit subtotal is USD 0.0000158, not a provider bill. Fresh production readback verified readiness, preservation of all six existing pools and aliases, fourteen backends, disabled streaming for both OpenRouter pools, and zero active/inflight reservations in every group. Independent review accepted staging and final production records, with no outstanding Critical or Major findings. The operator controls production intake reopening; the agent did not change external caller controls.

## Verification

The full suite passed with 2,531 tests, three skipped and nineteen deselected; runtime coverage was 90.08%. The four-slot harness passed five tests with 88.42% coverage, and 54 focused configuration/integration tests passed. Lint, formatting, type checks, Docker build and the Linux amd64 ACR build passed. The conditional Sonar script is absent. Independent reviews covered the plan, runtime changes, deployment packet, secret consistency correction, grant cleanup, staging evidence and final production acceptance.

The private deployment packet and execution records remain under `/private/tmp/production-two-release`; the bounded validation harness is included in the uncommitted changes at `scripts/quality/production_two_validation.py`.

Acceptance covers public responses and admin settlement observations. Independent provider observation, billing reconciliation, provider failover, OpenRouter streaming qualification, Table cutover and multiple-replica load remain unverified. Restarting staging with its stale OpenRouter seed would duplicate credit allocation and requires a fresh allocation review.
