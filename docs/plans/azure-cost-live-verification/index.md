# Azure cost read-only acceptance

**Implemented** locally; live acceptance attempted and remains unverified, 2026-10-08.
See [evidence](evidence.md). Verify the implemented [provider](../azure-cost-reconciliation/index.md)
using current developer Azure CLI identity and operator-supplied gitignored production resource
mapping. No permissions granted, deployments changed or router balances updated.

Use exactly two bounded Azure CLI metadata subprocesses, each with 15-second timeout,
64 KiB maximum captured JSON stdout and suppressed stdout/stderr/errors in user output.
Validate fixed Cognitive Services account operation and supplied scope arguments, no retries.
Kill/wait on timeout; reject malformed/oversize/mismatched metadata before billing calls.
Discover each of the two configured Cognitive Services resources using its supplied subscription,
resource group and name; use only the returned real resource ID and resource-group billing scope.
Do not display credential configuration, raw billing bodies, subscription/resource identifiers or
provider errors in committed evidence. Verify discovered kind/account metadata and exact unique
resource membership; fail before cost query on mismatch. Construct init-only billing configuration
using explicit operator cycle allowances/start days, disabling static overrides.

Run one complete provider refresh: at most two group queries with normal bounded pagination,
30-second total deadline, public ARM identity auth, no retries, 10 pages/10,000 rows/1 MiB per
page, USD-only resource-scoped ActualCost. Use AzureCliCredential only in this isolated read-only
verifier, not the production selector. Capture safe group IDs, cycle boundaries, labeled ceiling estimates, query success/failure categories, elapsed time and permission status.
The batch contains clamped ceilings only; never reconstruct reported cost by subtracting
the ceiling from the allowance. Query-time is not billing completeness; empty data/currency/resource/permission/pagination failure
remains unverified. Never apply returned ceilings to a running router or claim promotional balances.

Obtain independent plan review before verifier edits. Test discovered metadata validation and
numeric/redacted output with synthetic fixtures, then run read-only Azure acceptance under the
user's roadmap goal authorization. The existing async provider was fully verified locally;
no repeat Docker build is needed for a read-only script. Record exact scope/failures and commit.

- [Inputs](inputs.md)
- [Activities](activities.md)
- [Outputs](outputs.md)
- [Exit criteria](exit-criteria.md)
- [Risks](risk-register.md)
- [Evidence](evidence.md)

## Bounded diagnostic follow-up

The first generic failure did not identify its boundary. Read-only metadata preflight now
passes for both groups. After independent amendment review, perform exactly one additional
refresh using the same provider, scope, identity, pagination and deadline limits above.
Retain the first result unchanged; write a separate `diagnostic-results.json` artifact.
Use a whole-invocation OS lock and an atomically persisted started marker before external
calls; refuse existing started/result artifacts, including interrupted attempts. No overwrite
or resumed refresh. Cleanup failures retain the same conservative unverified status.
Report only fixed categories: metadata, identity, HTTP rejection, transport, schema, pagination,
cleanup or unknown failure. Map known internal error codes through a literal allowlist;
never emit exception strings, causes, raw response bodies, identifiers or credential values.
Do not loosen billing validation or change permissions in response to failure. An accepted
batch reports the existing labeled ceiling output only; never apply it to router balances.
