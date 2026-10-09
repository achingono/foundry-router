# Table entity write metadata boundary

**Planned**. Historical isolated-test logs show one selected request followed by an Azure
TableTransactionError400. The retained reservation was subsequently conservatively reaped,
clearing inflight and debiting0.03081USD estimate. This establishes Table transaction failure
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
full>=80%, Ruff/format/mypy, Docker, contextual review, links/operations/traceability.

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
