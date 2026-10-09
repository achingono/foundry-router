# Table real inference Evidence

Read-only inspection confirms separate existing real-test app uses memory/one and old verified
Responses image; cross-RG app uses synthetic Table/one. Existing test storage account is
HTTPS/TLS1.2 and shared-key disabled in shared RG. No configuration writes or inference yet.
Operator accepted the four-call/$0.15 estimate/output/retry limits on 2026-10-08.

## Prepared isolated deployment

- New app `foundry-router-table-real-261008`, one replica in the existing test environment.
- New tables `frTableReal261008health` and `frTableReal261008credit` on the discovered
  hardened cross-RG test account; two deterministic table-scoped grants for the existing
  real-test runtime identity. Parent storage/environment/registry/vault remain unchanged.
- Existing real-test secret versions pinned; two validated single-backend Azure models.
  Four maximum estimated reservations total $0.12544 at synthetic $10/$30 per million.
  This mapping does not establish fs-openclaw coverage, which remains open.
- Gitignored `infra/table-real-parameters.local.json` and `infra/table-real-inputs.local.json`
  contain references/configuration metadata only; no credential values written.
- Local amd64 build and network-disabled app/async Table import passed. Prepared image:
  `registry.example.test/foundry-router@sha256:b5af35885407bb0206176e79772030455f9d1557c8ce477c0fdf7afa145866c5`.
  This is a built manifest digest. Push is pending.
- ARM validation and final digest-pinned what-if: Succeeded. Proposed writes are exactly
  one app, two tables and two table-scoped grants; other listed resources are Ignore.
- Optional typed retry/reservation settings preserve existing defaults; test config uses
  retry0/reservation30s. Public and test Bicep compilation passed with existing CPU schema
  and experimental-assertion notices.
- Fixed verifier binds exact live deployment/image/identity/Table settings/pinned config before
  POST, validates strict private/result schemas, consumes bounded SSE incrementally, persists
  dispatched and observed accounting before later awaits, retains overrun/ambiguity and stops
  further traffic. Restart requires a changed ready replica/container identity or increased
  restart count before settled-estimate comparison; no post-restart inference.
- Eighteen focused tests pass. Ruff lint/format and strict mypy pass. Contextual independent
  implementation review cleared all Critical/Major findings after accounting/deployment/deadline
  and restart evidence fixes. SonarQube script is absent. Final full suite: 1,860 passed,
  3 skipped, 18 deselected; coverage 89.73%.

No image push, resource deployment, restart or Table-backed inference has been performed.
Concrete deployment approval is the next gate after recording final local verification.

## Current reviewed runtime image refresh

The earlier prepared digest above is superseded for the pending deployment by the
[reviewed image refresh](../table-real-image-refresh/evidence.md). Current runtime manifest:
`registry.example.test/foundry-router@sha256:d8f68e5c638510a38ad30c3cadb80d96bd97ae1936a46c75083ac1b7d59fd438`.
Platform/config/layer hashes and network-disabled imports passed. Private image/fingerprint
updated without changing any other parameters or models. ARM validation and finite read-only
what-if succeeded with the same one-app/two-table/two-grant scope. Push/deployment remain
pending approval of this current digest; earlier evidence remains historical.

## Approved isolated execution, 2026-10-09

Operator explicitly approved the isolated Table image push and deployment after the refreshed
digest and one-app/two-table/two-grant scope were presented. The four Azure inference calls
retain the previously accepted limits: zero retries, at most1,024 output tokens each and
$0.15 total estimated cost. Approval covers this isolated test, not production cut-over,
scale-out or a collector deployment. Image push/deployment execution is now underway.

## Runtime-mode preflight amendment

Independent plan and contextual review cleared checks for the actual runtime setting names
`FOUNDRY_RATE_LIMIT_BACKEND` and `FOUNDRY_TELEMETRY_ENABLED`. Explicit Table quota or enabled
telemetry now rejects; missing/memory/disabled values retain the intended test defaults.
Fifteen independent deployment mutation/default fixtures cover Table mode/names, retries,
reservation age, image digest, identity, pinned secrets, ingress and optional modes. Combined
binding/verifier focused selection: 33 passed. This changes verifier-only code, with no image,
deployment parameters or external approval scope change. Full verification: 1,891 passed,
3 skipped, 18 deselected; coverage 89.73%. Ruff lint/format and strict mypy passed.
