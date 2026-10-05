# Tools and Multimodal Outputs

## Mandatory Outputs

| Output | Description | Format |
| --- | --- | --- |
| Verified contracts | Dated provider/model/client matrix; tools, schemas, signatures and media forms; unsupported combinations | Markdown and strict synthetic fixtures |
| API decisions | Reviewed carrier/public media schema decisions; native surface justification only if needed | ADRs |
| Capabilities and admission | Explicit feature profiles/combinations, bounded validation, caller binding if needed, modality estimates/prices | Python and configuration docs |
| Increment A | Function declarations/calls/results, parallel/SSE assembly, structured output, required continuation replay | Adapter code and client/unit/integration tests |
| Increment B | Independently gated image/PDF intake, bounded metadata validation and conservative accounting | Adapter/media helper code and synthetic media tests |
| Increment C | Per-format audio/video input and image/audio output; native adapter only where justified | Separately reviewed code/tests per enabled capability |
| Operational documentation | Public subset/extensions, client support, feature rollout/rollback, key expiry/rotation and diagnostics | Canonical Markdown docs and synthetic examples |
| Verification | Per-increment quality/coverage/build results, independent review dispositions and separate live evidence | [Evidence](evidence.md) |

Increment C decisions are required planning outputs; implementation output is complete only
for capabilities whose schema/resource/accounting gates close. A decision to defer leaves that
capability **Planned**, never **Implemented**. The same rule applies to signature-dependent clients.

## Optional Outputs

- A representative coding-agent example after exact tool/signature replay has been verified.
- Opt-in live smoke runner with bounded traffic and harmless caller-side fixture tools.

## Output Quality Checklist

- [ ] Outputs reviewed and linked for every claimed increment/capability.
- [ ] Deferred formats and unsupported clients explicitly listed.
- [ ] Current evidence distinguishes design, code, client mocks and live-provider outcomes.
