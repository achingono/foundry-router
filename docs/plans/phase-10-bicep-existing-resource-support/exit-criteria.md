# Phase 10 Exit Criteria

## Gate Checklist
- [ ] `az bicep build` and `az bicep lint` complete with no new errors or warnings introduced by this phase, evaluated against the committed `infra/bicepconfig.json`.
- [ ] `infra/bicepconfig.json` is committed, enables assertions, and records the minimum Bicep / Azure CLI version.
- [ ] `az deployment group validate` passes for all four mode combinations: `new`/`new`, `new`/`existing`, `existing`/`new`, `existing`/`existing`.
- [ ] No free-text image reference parameter remains; every image reference is derived from either a resource login server or the validated `registryServer` parameter.
- [ ] `az deployment group validate` passes for secret-mode pull against an external server value.
- [ ] The daily cap parameter validates; the 90% alert query runs cleanly against the `Usage` schema; a cap-hit drill (what to check, in what order) is documented.
- [ ] `ContainerAppConsoleLogs` is on the `Basic` plan with 30-day retention; pay-as-you-go SKU is unchanged; the revert-to-Analytics path is documented.
- [ ] Per-request stdout volume is measured from a load run and recorded; the cap value traces to that baseline plus headroom.
- [ ] Uvicorn access logs are off in the deployed image; production `INFO` no longer contains per-request candidate arrays; focused tests cover the level gating and the 80% coverage bar holds.
- [ ] Over-length vault name, malformed registry name, and managed-identity pull against a non-Azure registry each fail validation with an actionable message.
- [ ] Registry pull succeeds with the system-assigned identity and no registry credential stored in the template.
- [ ] Secret-mode deployments source the credential only from a gitignored override or workflow secret; no credential value appears in any committed file.
- [ ] Key Vault secret references resolve (full entry shape including `identity: 'system'`) and the app starts with secrets injected via `secretRef`.
- [ ] Role assignments are idempotent across a second deployment of the same template, and are scoped to the registry and vault resources rather than their resource groups.
- [ ] A clean first deploy into an empty resource group converges without manual retry; any transient `ImagePullBackOff` is documented and distinguished from a true crash loop.
- [ ] No secret value appears in any template, parameter file, or workflow file.
- [ ] `*.local.json` parameter overrides are ignored by git and confirmed untracked.
- [ ] Committed parameter files and documentation contain placeholders only; a diff scan finds no live-environment resource name, ID, tenant or endpoint.
- [ ] `infra/parameters.example.json` exists and is placeholder-only.
- [ ] Each documentation delta (`infra/README.md`, `solution-structure.md`, `security.md`, `operations/index.md`) is individually reviewed, and each new requirements-traceability row is present.
- [ ] The workflow's Bicep validation job succeeds without access to any environment-specific resource, and its Azure authentication is verified working.
- [ ] Focused tests, full verification suite, lint, format, type check and Docker build all pass.
- [ ] `scripts/quality/sonarqube-scan.sh` executed if present, with all `Blocker`, `Critical` and `Major` findings addressed.
- [ ] Deep review executed if the prompt exists, with findings addressed.
- [ ] `maxReplicas` is capped at `1` by decorator; `az deployment group validate` with `maxReplicas=2` fails with a message referencing Phase 11; every committed parameter file sets `1`.
- [ ] `activeRevisionsMode: 'Single'` is explicit; after a deployment, `az containerapp revision list` shows exactly one active revision receiving 100% of traffic; the Dockerfile entrypoint stays single-worker; the rollout-overlap window and per-revision credit reset are documented in `infra/README.md`.
- [ ] Role assignments on `existing` resources in another resource group deploy through a module scoped to that group, validated cross-group, with deployer permissions documented.
- [ ] Every document listed in activities step 16 labels the deployed multi-replica capability `Partially implemented` with a Phase 11 reference, while adapter code stays `Implemented`; a repository search finds no remaining claim that Table Storage multi-replica state is deployed or verified.
- [ ] Documentation and traceability updated, with no unsupported present-tense claims.
- [ ] Plan reviewed by an independent session before implementation began.

## Approval Table

| Role | Name | Status | Notes |
| --- | --- | --- | --- |
| Owner | | Pending | |
| Reviewer | | Pending | |
| Approver | | Pending | |
