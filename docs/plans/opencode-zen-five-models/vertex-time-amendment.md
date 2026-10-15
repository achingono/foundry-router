# Vertex native creation-time metadata amendment

Status: Planned pending independent approval.

The first replacement Flash nonstream slot also failed HTTP502 and is permanently consumed. Its drained stage remainder is0.095514USD after a measured0.000468USD debit. Staging is stopped; production remains unchanged. The documented Google modelStatus correction was insufficient to make this provider response compatible, and is not claimed as the cause.

Read-only public Vertex v1 discovery confirms native `GenerateContentResponse` includes optional `createTime`: a timestamp for when the server received the request. Together with the original diagnostic's exactly one unknown envelope field and valid STOP/text/usage, this suggests the OpenCode response may be Vertex-shaped. No raw output or unknown field name was retained, so compatibility remains a live acceptance gate.

Accept only documented `createTime` metadata in the shared native envelope validator: bounded128bytes, string type, strict RFC3339 date/time with timezone and valid calendar/time; ignore it in public output/state/logging. Validate every stream envelope, including usage-only events. Preserve existing bounded modelStatus and rejection of all arbitrary unknown fields. Add tests for UTC/fractional/offset timestamps and malformed/null/oversize/tz-less dates across nonstream/content/usage-only stream.

Add exactly one recognized new acceptance identity `opencode-zen-five-20261013-vertex-time`, eighteen fresh cases, identical roster/request/token/time/price/reserve, fixed staging0.095514USD and production9.90USD. Require exact binding to both failed original manifests/ledgers, original consumed diagnostic, latest stopped snapshot, and exact debit arithmetic. Preserve every historical artifact and no replay. No extra diagnostic call; no replenishment/transfer. Rebuild/test/review immutable image and concrete packet before nine staging cases. Failed or ambiguous cases halt all remaining calls. Production handoff needs remediation of prior operational Majors (explicit successful empty replica enumeration; barrier snapshot hash verification through final handoff) before any transition.

Source: `https://aiplatform.googleapis.com/$discovery/rest?version=v1`, `GoogleCloudAiplatformV1GenerateContentResponse.createTime`, read October13. No actual field-name diagnosis is asserted.
