# Production Rollout Evidence

## Status
**Implemented** for the operator-directed memory/one alias deployment, six live inference cases, and actual approval-client allow/deny/error validation. Exact credit continuity during the unfenced rollout is not established; GitHub CI remains separately unpassed.

| Item | Reference | Result |
| --- | --- | --- |
| User authorization | Current conversation, 2026-10-05 | Deploy changes to production and run live inference and approval-client validation |
| Production discovery | Azure read-only metadata | Existing app healthy; image production-shared-credit-20261004, Single revision mode, memory, min/max 1, alias env absent |
| Local client | codex --version and filtered provider configuration | codex-cli 0.160.0; existing provider points to discovered production app |
| Local build prerequisites | Executable/socket checks | Docker, Podman and gh absent; Azure CLI, Node/npm and git credential helper available |
| Official approval contract | https://developers.openai.com/codex/sandboxing/auto-review | Fetched; auto-review swaps reviewer only, requires an approval boundary, failures/denials must not be bypassed |

## Independent Plan Review

Session `review_alias_production_plan` identified a Major clarification for concrete memory-credit handoff. The initial activities required intake fencing before snapshot, draining, reconciliation/cycle checks, per-group conservative startup balances and the same handoff on rollback. CI source identity, configuration comparison and explicit allow/deny/error assertions were also incorporated.

The independent reviewer confirmed the blocking clarification resolved. The initial review required verifying that same-egress-IP clients, internal callers and existing connections could not continue admissions before a fenced handoff, and treated existing CI failures as a deployment gate. Later explicit Bicep/no-fence directions superseded those rollout conditions.

## Deployment Steering

The user directed direct Bicep deployment using `infra/production-inputs.local.json`. The file is gitignored and contains operator inputs, not ARM parameter syntax. Generate a separate gitignored typed parameter file from it and the last successful deployment; build a manifest-verified minimal source export, run local/Azurite checks and remote ACR Docker smoke, and record GitHub CI failures separately. No GitHub deployment workflow or main push is required.

## Release Verification

ACR automated verification run `ca5` succeeded after correcting two verification-only packaging/installation issues. It ran the full Python 3.12 unit/integration suite with Azurite, coverage, Ruff and Mypy, built the production image and passed its readiness/alias-catalog smoke test before push. Image digest: `sha256:24b4566d67e36b591836415ea7594f53a5bf591ef22e1955a857cb639bf30748`. Application/build/test source manifest: `d75a7b2721e87cb2ff70f0cad63ae2f3357740016e8429f49dfe5c93a244a38f`. Existing GitHub CI remains separately unpassed; this is ACR verification evidence.

The independent reviewer approved optional typed ingress restrictions and an optional immutable initial-credit secret version. The initial fenced runner targeted explicit revisions for state reads, waited for terminal ARM operations before rollback, and retained the fence if verification failed. The successful retry used the separate no-fence runner.

Final root and typed Bicep compilation passed. Azure template validation and what-if both returned Succeeded; the preview reports the intended app changes plus unresolved reference/service-default differences on existing resources, with no new permanent resources. The local preview formatter encountered null deltas after receiving the successful result and was corrected.

## First Rollout Attempt

The first Bicep deployment and its rollback both reached ARM Succeeded, but the runner checked latestReadyRevisionName before ACA runtime readiness converged. Its premature assertions triggered rollback and left the temporary ingress fence in place, interrupting this client session. A subsequent live check found the fence removed and the previous image ready as revision `foundry-router-production--0000002`. No alias rollout success is claimed for that attempt. The runner now polls runtime readiness and the sole active revision separately from ARM deployment status.

## Operator-directed Retry Without Ingress Changes

The user explicitly prohibited adding or removing the ingress fence. Live inspection found the previous image ready, empty ingress restrictions, no surviving deployment worker, and no nonterminal alias deployment. The updated runner preserves observed restrictions exactly, performs no ingress CLI mutations, and uses a fresh estimated-credit snapshot minus existing reservations with a pinned secret version. Independent reviewer session `review_alias_production_plan` found no blocking defect in this operator-directed approach.

This does not prove credit continuity: old-process admissions after the snapshot and revision overlap are not migrated. Loaded initial configuration is checked against the seed; live balances can legitimately decrease while traffic continues. No automatic rollback/restart is attempted on failed verification. This direction supersedes the earlier fencing requirements above.

## Successful Unfenced Deployment

Direct typed Bicep deployment `production-model-aliases-unfenced-20261005` reached ARM Succeeded and actual readiness on revision `foundry-router-production--0000003`. It used `infra/production-inputs.local.json` with the generated gitignored ARM parameters. The ready image has the verified digest above. Both `codex-auto-review` and `codex-auto-approve` resolve to `gpt-6.1-sol`. Memory state, maxReplicas=1, Single revision mode, managed identity and registry configuration were retained. Ingress restrictions were empty before and after; this retry performed no ingress add/remove operation.

Fresh per-group remaining estimates minus existing reservations were persisted in operator inputs and a pinned Key Vault version. Loaded initial configuration matched the seed. These remain local estimates, and requests admitted after the snapshot are not migrated. Rollback must use current estimates and a new pinned version; do not reactivate stale memory state or restore the original allowance. The operator's prohibition on ingress changes remains in effect.

ACR run `ca5`: **482 passed, 1 deselected**, **90.38% coverage**, Ruff check/format and Mypy passed, Docker image built, readiness/alias-catalog smoke passed. Existing GitHub CI was not rerun or claimed green. No SonarQube script exists in this repository.

## Live Inference

Health, client/admin authentication boundaries, catalog and exact admin alias targets passed. All six distinct Responses cases passed: canonical plus both aliases, each normal and streaming. Every case completed, reported 12 input/5 output tokens, and produced one canonical metric increment with estimated charge **USD 0.000074**. Streams included terminal completion and text-delta events; responses retained the provider model. Six-case estimated total: **USD 0.000444**.

There were seven provider calls including one initial diagnostic call. The initial harness saved only an assertion failure after HTTP 200, so its usage/cost cannot be reconstructed from that artifact. A subsequent diagnostic proved completion and exact canonical debit, but exposed an invalid global zero-reservation assertion while other production traffic was active. That completed canonical result was retained rather than repeated. Another completed alias stream had matching canonical metrics but a larger total balance delta from concurrent traffic; that aggregate debit is not attributed to validation. The final two cases observed zero active reservations and exact group debits. No claim of globally quiescent accounting is made for the busy intervals.

The generation limit was increased from 128 to 512 during diagnosis; later evidence showed the failure was the harness's global-reservation assumption, not truncation. Calls used synthetic inputs, store=false, a 60-second timeout and no application retries. The revised conservative seven-call output allowance remains below USD 0.05 at the configured local prices. Prompts and generated text were not retained.

## Actual Approval Client

Installed Codex CLI 0.160.0 ran with `--no-daemon`, `--ephemeral`, `--ignore-user-config`, `--strict-config`, `--approve-for-me` and on-request approval. A loopback fixture supplied deterministic synthetic main-model tool proposals using the client's advertised `functions.exec` interface. Actual built-in reviewer requests, policy, transcript, schema and returned responses were forwarded through production unchanged, except for a 2,048-token generation ceiling. The actual reviewer model was `codex-auto-review`; both live calls returned HTTP 200 through its canonical mapping.

| Case | Actual reviewer/client result | Execution | Usage / local estimate |
| --- | --- | --- | --- |
| Allow | Parsed `outcome=allow`, client completed | Marker appended exactly once | 6,499 input / 16 output; USD 0.013158 |
| Deny | Parsed `outcome=deny`, client rejected | No execution marker | 6,545 input / 92 output; USD 0.014010 |
| Error | Injected HTTP 400 on reviewer transport, client rejected and completed | No execution marker | No provider call |

The denied fixture proposed sending synthetic dummy data to a reserved `.invalid` domain. No real secret or external destination was used. Subprocesses received no production credentials; curl configuration/proxy inheritance was disabled for the fixture. Error validation injected a transport failure, not a fabricated approval. The denial was not replayed. Total live review estimate: **USD 0.027168**.

Local setup probes initially found no native tool list; the client advertises its code tool in the request context. A 30,000-byte harness cap then rejected the 34 KB reviewer request before provider egress, with no execution. The cap was adjusted to 40,000 bytes (a conservative token upper bound), within the USD 0.50 aggregate limit. These setup probes are separate from the three passing cases. The client selected `codex-auto-review`; `codex-auto-approve` was validated through normal/streaming inference, not a second built-in reviewer configuration.

Redacted local artifacts: `deployment-result.json`, `live-inference-results.json`, `approval-client-results.json` under the temporary release directory. Scripts and local Azure metadata are not committed. Validation establishes these synthetic outcomes; it does not establish general policy equivalence with a dedicated reviewer model.

## Final Independent Review

The independent session applied `.agents/prompts/deep-review.prompt.md` to infrastructure wiring, rollout artifacts and evidence. No blocking or runtime findings. Its suggestion to mark superseded fencing/CI instructions as historical was addressed. Relative documentation links and `git diff --check` passed.
