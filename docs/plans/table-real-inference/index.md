# Isolated Table-backed real Azure inference

**Partially implemented**; approved isolated deployment passed on2026-10-09, live acceptance
failed/unverified. Model-1 returned503 with retained reservation; model-2 has an ambiguous
started entry. Streaming/restart withheld; no replay. See [evidence](evidence.md).
Required roadmap gate 4a. Production remains memory/one. See [evidence](evidence.md).
The operator authorized four requests across the two existing real-test model configurations,
zero retries, at most 1,024 output tokens each and $0.15 total local estimated cost.

Prepare a separate one-replica test app in the existing test environment. Reuse discovered
real-test registry and user-assigned runtime identity/Key Vault references, existing hardened
cross-RG test storage account, and two new app-specific health/credit tables. Never attach
existing synthetic or production table names. No storage account/environment/logging writes;
table-scoped identity grants only, deterministic and idempotent. Fresh tables prevent old
synthetic credit state from being mistaken for real-inference accounting. Reuse identity only
within this isolated test scope; verify existing registry/vault access and no operator data grant.

All subscription/resource/identity/image/secret IDs and endpoint values come from current Azure
metadata into gitignored bounded inputs; no invented IDs or credential values in evidence.
Resolve/pin all eight existing test secret versions without printing contents. Safely inspect
backend/model/pricing/cycle configuration in memory, validate exactly two intended models,
Azure-only pools, supported Responses endpoints, explicit pricing and finite estimated reserves.
Keep test estimates labeled synthetic. Reusing configuration does not establish fs-openclaw
coverage; include it only if validated exact backend/model mapping supplies it. Otherwise retain
that specific roadmap gate. No Google, embeddings, media or production traffic in this phase.

Deploy a linux/amd64 image built from the reviewed current revision, pinned by registry digest.
Prepare a small test-only Bicep composition of existing identity/router/table modules, with
required scalar overrides retry_attempts=0 and reservation lifetime=30s (the existing routing
execution deadline deducts its bounded settlement margin). Keep client case deadline30s.
If the shared router
module cannot accept these settings, add optional typed fields preserving existing defaults
and run relevant contract tests/full quality/Docker/deep review. Quota stays memory/one;
cost provider stays static; no collector or distributed quota deployment in this phase.

Deployment preflight must check the actual runtime setting names
`FOUNDRY_RATE_LIMIT_BACKEND` and `FOUNDRY_TELEMETRY_ENABLED`, rather than invented
quota/exporter aliases. Missing values preserve memory/disabled defaults; explicit nondefault
values reject before inference. Regression fixtures must mutate the live Table mode, tables,
image digest, identity, secret versions, optional modes and ingress independently, proving
each wrong deployment fails binding without provider traffic. Keep approval scope unchanged.

Before requesting external-write approval, finish template/parameters/scripts/review,
local verification, ARM validation and what-if, and present exact app/tables/grants/image
scope. Approval applies to the concrete isolated deployment and image push, not production.
Use existing app ingress restrictions; verify resulting endpoints from deployment outputs.

After approval/deployment, require readiness/auth/model/status checks before any inference.
Use a durable invocation ledger with immutable configuration/digest fingerprint; reserve each
of four deterministic model/stream cases before dispatch. No retries or replacement of ambiguous
requests. Cap input64 tokens, output1,024, total1,088 per case, body4KiB, response4MiB,
30s total case deadline. Reserve price-based maximum against $0.15 cumulative estimate;
refuse before dispatch if any projected maximum cannot fit. Actual observed usage can only
increase a retained debit if above reserve; overrun stops the whole stage. Unknown usage retains
full debit. First failure/ambiguity stops that model; streaming only follows its passing nonstream.
Set router intake auth and retry0; one isolated app/client worker. Require an OS whole-stage
lock and atomic write/flush/fsync/replace of ledger and results before the next case. Persist
dispatched requests before awaiting transport; ledgered requests without results remain ambiguous
and never resume as new traffic. Validate saved result schema/binding before displaying it.

Consume SSE incrementally without buffering all upstream output. Require terminal completed
response, nonempty public text, bounded valid input/output usage and correct estimated debit.
Read authenticated status before/after each request, attributed configured backend, unchanged
unselected balances, zero active/inflight reservations. Before ALL inference, require each
validated effective model pool to contain exactly one backend, with no alternate candidates
or aliases. Retry0 does not disable routing failover on 429; a single-backend pool prevents
extra provider dispatch. If existing configuration has multiple candidates, prepare a private
copy with explicitly selected single-backend pools and obtain concrete approval before any
traffic; otherwise stop the whole stage. Never persist prompts, outputs, keys, full backend
configuration or provider errors. Persist safe labels/counts/flags/digests only. No arbitrary
operator endpoints or command injection; validate fixed Azure host/path/resource scopes.

After passing cases, restart only this test app via targeted replica/container action and
verify readiness, unchanged settled estimates and no reservations. No additional inference
requests after restart. Keep test tables/app for evidence; cleanup requires its own explicit
scope and never deletes existing-account parent or other tables. Provider 429/failure/admission,
Table concurrency/scale-out, cost acceptance and production go decisions remain separate.

- [Inputs](inputs.md)
- [Activities](activities.md)
- [Outputs](outputs.md)
- [Exit criteria](exit-criteria.md)
- [Risks](risk-register.md)
- [Evidence](evidence.md)
