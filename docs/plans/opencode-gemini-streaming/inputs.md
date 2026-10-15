# Gemini streaming Inputs

## Required Inputs
| Input | Source | Owner |
|---|---|---|
| ca6 staging manifests/ledgers, stopped proof, zero-reservation snapshot | `docs/plans/opencode-zen-five-models/evidence.md:53`, actual stored artifacts | coordinator |
| Vertex-time stream failure record (Flash nonstream 7in/78out pass; next stream 502, full 0.003855 reservation settled/cleared, writer stopped) | `docs/plans/opencode-zen-five-models/evidence.md:41` | coordinator |
| Current streaming decoder source | `src/foundry_router/api/adapters/google_native.py:690-748` | coordinator |
| Prior nonstream structural diagnostic pattern | `scripts/quality/opencode_five_diagnostic.py` | coordinator |
| Actual isolated-staging stopped snapshot + measured remaining before diagnostic spend | operator-provided, not invented | operator |
| Fresh OpenCode key out-of-band; fixed synthetic text, max_output_tokens 512, deadline 120s | operator | operator |
| Diagnostic packet: new identity/path, code/native-body/profile/pricing hashes, ca6 source-artifact hashes, actual R and conservative D, reserve and later-stage budget arithmetic | coordinator; independently reviewed before dispatch | coordinator |
| New eighteen-slot identity, exact nine-case ordering per environment, both Gemini streaming policies, fixed post-diagnostic S <= R-D | acceptance contract in [activities](activities.md) | coordinator |
| New image digest, private full staging configuration and both policy fingerprints | verified build/release packet; required before staging | coordinator |
| Updated production packet, operator drain continuity evidence, final fresh inherited seeds and immutable full-payload handoff | inherited five-model procedure; required before promotion | operator/coordinator |

## Optional Inputs
- Public Google/OpenCode SSE documentation excerpts dated at read time (illustrative only).

## Input Validation Checklist
- [ ] Historical artifacts retain their actual original bindings; new packets bind the candidate image, not ca6 as the runtime under test
- [ ] All inputs for the next execution gate are complete and independently reviewed; pending later-stage inputs do not authorize that stage
- [ ] Prior ledgers/manifests preserved unmodified; no replay authorized
- [ ] Staging writer verified stopped with zero reservations before spend
- [ ] Complete historical chain, new irrevocable diagnostic debit, reserve and remaining stage budget verified; production allocation never reused
