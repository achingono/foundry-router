# Evidence

Status: Planned. Discovery only for five-model scope.

- Existing Argon dirty implementation/tests/docs retained; previous measured evidence stays under its plan.
- October13 current OpenCode model table/catalog HTTP200 confirmed all five exact IDs/routes/prices. No paid calls in discovery.
- Reserve $0.05/5% and deployment timing approved directly by user. Current account amount10USD confirmed directly by user.

Initial independent review found two Majors; amended plan uses Sonnet input4USD/M conservative cache-write ceiling and an explicit ingress deny barrier with preflight localhost admin exec, continuity checks and snapshot-before-stop. Re-review pending.

## Local measured verification

- Independent amended-plan review approved implementation, both initial Majors resolved.
-50 Anthropic unit/integration tests passed;105 combined native Google/Anthropic checks passed after correcting an expected public400 streaming-policy assertion (adapter-level rejection remains422).
-11 durable-runner tests passed; runner coverage89.86%. Initial coverage invocation named the wrong import-qualified module and collected no data; corrected invocation measures the actual imported module.
-Full repository suite:2647 passed,3 skipped,19 deselected (not Docker/Azurite), runtime coverage90.20%. Ruff lint/format (209 Python files) and strict mypy73source files passed; git diff--check clean.
-Immutable Linux/amd64 ACR build is in progress; no production mutation or live model inference has occurred.
-Read-only current admin shows existing production traffic; quiet snapshots are not claimed. Targeted replica exec channel connected successfully but startup argument preflight is still being resolved, with no ingress change.

-The Linux/amd64 ACR candidate buildca2 succeeded, digestsha256:9c654ff7cc87ae5a01d8aad041721039f0f1cc2a8ec9d12b5678b8c66e58e577. It has not been promoted.
-Independent implementation review found a Major runner terminal-validation error-path gap; exception now forces failedstatus, and a bound+1 output-usage regression test consumes one slot and prevents the next. Focused runner re-verification passed.

## Current measured state (October 13, 2026)

Runtime implementation is **Implemented**; five-model production rollout remains **Planned**. Final runtime suite before image build: 2649 passed, 3 skipped, 19 deselected, runtime coverage 90.20%; runner 12 passed, coverage 90.60%. Final Linux/amd64 ACR build ca3 succeeded with digest `sha256:a91fc53fac19212103ada1f304b492b6f6c9be355a766f87351859a68e290aec`. The earlier ca2 digest is obsolete after nullable Anthropic input corrections. Final image was pulled and isolated Docker staging was ready.

Independent packet review approved the original bounded staging run. Its first slot, `staging-0-nonstream`, failed: native OpenCode Gemini Flash returned HTTP 200; the router returned HTTP 502 without accepted public usage/output. Estimated local debit was 0.000018 USD; reservations cleared. The immutable original run remains failed and is never reset or replayed. No other original acceptance slot was dispatched. Failed staging writer was stopped with 0.099982 USD local estimated remainder. Production configuration, ingress and revision remain unchanged; no drain/promotion occurred.

A separately reviewed one-call structural diagnostic is being prepared to establish the incompatibility. Its conservative irrevocable 0.004 USD debit would leave 0.095982 USD in the original staging portion, while production's conservative 9.90 USD seed stays fixed. The diagnostic emits only allowlisted structure, numeric usage and finish enums; no model text, prompts or credentials. The direct independent review reports are retained; all reported Majors are being remediated before dispatch. App review-agent turns also failed through the existing router's insufficient Azure credit capacity, so independent read-only CLI sessions use the operator's direct Foundry configuration.

The single diagnostic completed after independent approval: HTTP200, one STOP candidate with text/signature, usage7input/1output, and one unrecognized envelope field. Native translation rejected the envelope. Unknown field names and all text remained suppressed. Public Google discovery schemas document `modelStatus`; the metadata amendment was independently approved as a plausible, bounded compatibility correction, not a proven field-name diagnosis.

The correction validates/drops documented model-status metadata for nonstream, content-stream and usage-only envelopes. Focused92tests passed. Final non-Docker/Azurite suite2678passed,3skipped,19deselected; final coverage measurement is running. Runner+diagnostic26tests passed, coverage91.50%/99.11%. Ruff/lint/format and mypy73source files passed. Final candidate ca4 Linux/amd64 build succeeded: `sha256:5d88b363deae42e1d24179b8fd9f38f9bf7b981f37d6daab4dbf525c19fa1a6c`. Prior ca3 is preserved but superseded for this corrected candidate. Fresh isolated staging is ready, with recognized replacement identity and fixed0.095982USD seed bound to original failed ledger, consumed diagnostic and stopped snapshot; original artifacts were not overwritten.

Read-only Azure checks found existing operator Owner/Key Vault Administrator permissions, so no temporary vault grant is necessary. Current environment has no VNet integration; ingress resolves only IPv4. These preflight checks do not claim that the drain barrier or production promotion has occurred.

The modelStatus replacement's first Flash nonstream case failed502 again; no other replacement slot was dispatched. Measured local debit0.000468USD; zero reservations; writer stopped with0.095514USD remaining. Thus modelStatus is not established as the incompatibility's cause. Read-only Vertex v1 discovery documents optional createTime in its native response, absent from the adapter. The strict timestamp amendment was independently approved before implementation; it validates/drops bounded RFC3339 metadata across nonstream/content/usage-only stream and preserves unknown-field rejection.

Timestamp-focused87tests passed, full suite2692passed/3skipped/19deselected with90.23% runtime coverage. Lint/format/types pass. A recognized third immutable acceptance identity has fixed0.095514USD staging seed, backed by both actual failed manifests/ledgers, original diagnostic and latest stopped snapshot; fixed production9.90USD remains unchanged. Build/packet review and live acceptance remain gates. Prior live evidence and consumed identities remain unmodified.

Vertex-time Flash nonstream passedHTTP200/completed/validusage7input78output with0.0005955USD debit, establishing that model's nonstream compatibility for ca5. Its next stream request returned502 before public output; a full conservative0.003855USD reservation settled and cleared. No further Vertex-time slot was dispatched. Writer stopped; actual localremaining0.0910635USD. Native Gemini streaming remains unverified.

Operator was offered an optional choice of immediate Gemini nonstreaming deployment or finishing streaming first; no streaming requirement was in the deployment request. After reasonable opportunity, the coordinator proceeds with recommended nonstream deployment, subject to later operator steering. Independent plan approved a fixed14-slot/seven-per-environment scope: Gemini512nonstream, Sonnet128nonstream, Grok/Muse512nonstream+stream. Both Gemini pools are explicitly streaming-disabled. Fixed stage0.09USD rounds the measured0.0910635 down;0.0010635 is not refunded or transferred. Original histories and diagnostic remain consumed/unmodified. Full final suite2694passed,3skipped,19deselected; runtimecoverage90.23%. Runner/diagnostic29passed with92.22%/99.11%coverage. ca5 runtime image remains unchanged.

Independent timestamp review's nonblocking suggestion is recorded as deferred: malformed timezone-offset minutes may normalize in Python's parser. This affects bounded discarded metadata only, not inference content/credentials/credits; the reviewed runtime image is preserved for deployment. No claim of accepting every valid or rejecting every invalid RFC3339 spelling is made.

Read-only inactive-replica API probes found no inactive revision in either production or the historical stopped staging app, so those probes did not establish empty-replica behavior. Actual old-writer deactivation must still produce successful explicit empty replica enumeration; absence/error is not treated as zero. Production transition remains gated accordingly.

The seven-case Gemini-nonstream staging identity passed Flash(7input59output,0.000453USD) and Argon(38input5output,0.000252USD). Sonnet nativeHTTP200 rejected at translation/public502, estimated debit0.000112USD. No later slot dispatched. Writer stopped, zero reservations, localremaining0.089183USD. Current public Anthropic schemas document nullable container/diagnostics/stop_details and nullable/emptycitations, previously unaccepted. Independent plan approved narrowly accepting only absent forms, while rejecting active state/citations/unknowns. The previous timestamp-offset suggestion is also corrected with explicit hour/minute bounds and regression checks.

Focused132tests passed; full final suite2718passed,3skipped,19deselected,90.23%runtime coverage; Anthropic adapter96.43%, nativeGoogle93.15%. Runner/diagnostic30passed,92.26%/99.11%. Lint/format/mypy73source files passed. New recognized14slot/seven-per-environment identity has conservative0.088USD staging seed (discard0.001183USD), fixedproduction9.90, samepolicies/requests/prices/reserve, and binds all four historical runs plus originaldiagnostic/lateststoppedsnapshot. Actual nativefield-name cause remains unproven pending live acceptance. No production mutation has occurred.

The nullable-metadata image ca6 `sha256:180b9d9efc0f5ccb01528ac8178ac28babae2470e991cbd34f212a22cad6d27e` passed all seven staging cases: Flash/Argon/Sonnet nonstream, Grok/Muse nonstream+stream. Each completed with text, valid usage and exact estimated debit; reservations cleared. Isolated writer stopped and no unused allocation transferred. This establishes ordinary-text staging inference for all five exact physical models, including Sonnet's corrected response handling.

Before production stop, CLI help confirmed revision list requires `--all` to include inactive revisions. The operational enumerator now uses that flag; earlier zero-inactive preflights used the default active-only list and did not prove inactive API behavior. Explicit successful empty replica enumeration remains mandatory for every inactive revision, including immediately before promotion.
