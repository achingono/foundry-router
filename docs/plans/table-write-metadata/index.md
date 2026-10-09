# Table entity write metadata boundary

**Implemented** (write boundary and supplemental live streaming); original full acceptance remains open. Historical isolated-test logs show one selected request followed by an Azure
TableTransactionError HTTP 400. The retained reservation was subsequently conservatively reaped,
clearing inflight and debiting 0.03081 USD estimate. This establishes Table transaction failure
and recovery, not the exact provider response or Azure error message.

Code inspection finds settlement intent copies a normalized read entity containing
`odata.etag`. The real SDK serializes this key into the JSON body, including
`odata.etag@odata.type`. ETag is concurrency metadata and must be sent through conditional
headers, not persisted as an application property. Azure property-name rules exclude periods.
Azurite accepted this payload in prior tests, so those passes did not prove cloud acceptance.

At AzureTableEntityClient's write boundary remove exactly read-only transport metadata
`odata.etag`, `odata.metadata` and `Timestamp` from
Create/Update/UpdateMerge/upsert/create-if-absent bodies. Preserve PartitionKey, RowKey and
all application fields, including an application property named `metadata`. SDK metadata
attributes are not part of dict(entity); a mapping-valued `metadata` application property is
unsupported by the SDK and must not be silently discarded. ETag kwargs/IfNotModified remain unchanged; missing balance ETags
still reject. Do not mutate supplied mappings or broadly drop arbitrary fields.

Independent review before implementation. Verify with real SDK serialization/recorded
HTTP transaction bytes that read-then-update settlement intent contains no metadata body
properties and still carries If-Match; cover conditional conflict/no mutation and full
credit finalize/recovery through a strict property-name fake and real local Azurite. Run
full coverage >=80%, Ruff/format/mypy, Docker, contextual review, links/operations/traceability.

Retain old live ledger and safe diagnostic evidence. No old request replay or manual balance
reset. Local correction cannot clear cloud acceptance. A bounded isolated synthetic Table
operation and updated test app may verify cloud write behavior under troubleshooting scope;
provider inference requires fresh reviewed remaining-budget cases. No production changes.

- [Inputs](inputs.md)
- [Activities](activities.md)
- [Outputs](outputs.md)
- [Exit criteria](exit-criteria.md)
- [Risks](risk-register.md)
- [Evidence](evidence.md)

## Isolated image correction and supplemental acceptance

Operator authorized troubleshooting the isolated Table failure. Publish the verified corrected
image and update only the existing isolated app image; retain identity, tables, single replica,
zero retries and all pinned model/pricing configuration. Bind deployed metadata before traffic.
Do not alter production or registry/table access scope.

The original ledger remains immutable, including the failed and ambiguous started nonstream
cases. A separate supplemental ledger may execute only the previously unattempted model-1
and model-2 streaming cases, after independent review and zero-active status checks. Retain
both original reservations as consumed budget: four total maximum router calls, 1,024 output
tokens each, zero retries and 0.12544 USD total maximum local estimate under the approved
0.15 USD limit. Persist each fresh case before dispatch; stop all supplemental traffic on
failure, ambiguity, overrun or incomplete settlement. Supplemental passes cannot reclassify
original failures or prove the full four-case acceptance/restart gate.

The corrected isolated image and both supplemental streaming settlements passed live.
See [evidence](evidence.md). Original nonstream failure/ambiguity and restart acceptance
remain open; the original four-request authorization is exhausted.
