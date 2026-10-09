# Evidence

Status: **Partially implemented**. Seven live canary prerequisite attempts completed; deployment and image publication were withheld after provider failures. No production mutation occurred.

Prior diagnostics and original budgets remain immutable. Production deployment is explicitly authorized in the current conversation. Review and verification results will be appended with exact scope.

Independent plan review cleared the separate Google-only app and atomic quota bootstrap. Focused runtime/lifecycle checks: 72 passed. Default-off failover tests: 19 passed. Bootstrap lost-acknowledgment/delayed rerun/rollover checks: 2 passed.

Public Google rate-limit documentation retrieved 2026-10-09 explicitly labels TPM as input tokens. Read-only Google API-key lookup with the Azure session token returned HTTP401; it does not establish key mapping. Selected project association remains operator-supplied.

First staging project3 nonstream returned provider/public503; natural cleanup and conservative settlement passed. Retained immutable stage-ledger.json. A separate reviewed recovery ledger uses at most two remaining retries for this logical case, three attempts for subsequent modes and at most six staging dispatches per project, leaving two/project for production. Same total16physical/20480token allowance applies; no diagnostic slots replayed.

## Final pre-deployment acceptance outcome

Status: **Partially implemented**. Production deployment was withheld after live prerequisite failures. No image was published, no Container App/configuration/secret/table/grant was created or changed. The separate Google-only canary remains a design target; existing Azure production remains unchanged.

| Project / operation | Result | Physical attempts | Scope |
| --- | --- | ---: | --- |
| Project3 nonstream | Failed | 3 | Google503 on all three; natural cleanup and conservative synthetic settlement passed |
| Project3 streaming/cancellation | Withheld | 0 | Nonstream prerequisite failed |
| Project4 nonstream | Passed | 1 | Provider/public200, aggregate usage and synthetic settlement, natural cleanup |
| Project4 streaming | Failed | 3 | Google503 on all three; natural cleanup and conservative settlement passed |
| Project4 cancellation | Withheld | 0 | Streaming prerequisite failed |

Retained artifacts: initial stage (local-only `stage-ledger.json`), project3 retries (local-only `stage-recovery-ledger.json`), project4 assessment (local-only `stage-project4-ledger.json`). Total7physicalattempts/8960reservedtokens, within16physical/20480reservedtoken combined allowance. These are fresh canary attempts, not replayed diagnostic slots. Both failed logical combinations exhausted three attempts; remaining global headroom does not reopen them. No prompts, outputs or credentials retained.

The stream verifier fed Google's503 error body through its SSE observer, causing the local public fixture to return500 rather than preserving503. Provider503 was observed and recorded directly; this is a verifier limitation, not evidence that production returned500. It does not establish a successful stream, early delivery or cancellation. Failure bodies were not retained.

Verification: full suite2131passed/3skipped, coverage90.16%; Ruff check and formatting pass, mypy70sourcefiles pass. Linuxamd64 Docker build and network-disabled aggregate usage import smoke pass. Local imagefoundry-router:google-canary, OCI indexsha256:f7c1f37d3687dd882eb795cb09824162ca2f3f07770405f4c9b38b772a3cd895; not published or deployed. Sonar scanner absent. Runtime failover/bootstrap independently reviewed; staging and bounded retries cleared after fixes.

Next work requires a new bounded availability/acceptance run for the failed combinations after provider recovery. Do not deploy this canary before complete nonstream/stream/client-cancellation acceptance. The operator's deployment authorization remains in effect, but elapsed time or spare global tokens cannot satisfy a failed technical gate. 3.7 and collector/scale-out remain deferred. Deployment prototype removed because prerequisite gates failed; no unreviewed mutation runner is presented as deployable.

Final independent contextual review: no outstanding Critical/Major findings. Opening status corrected to match retained seven-attempt evidence; relative links and exact-secret scan passed.
