# Google 3.8 Responses diagnostics

**Planned**. Operator explicitly requests fresh 3.8 diagnostics and availability through the
router. Historical successful native calls and intermittent provider 503/UNAVAILABLE do not
prove compatible Responses behavior. All previous execution ledgers remain immutable and
exhausted. This newly authorized diagnostic run has a separate finite ledger, not a reset.

Use the existing referenced five-key free-tier array, projects 1 and 2 only. At most three
new calls per project (six total), 1,024 output tokens and 64 estimated input tokens each;
reserve 1,088 tokens per call, maximum 6,528 reserved tokens total and zero paid spend.
No retries, ramps, quota-exhaustion probes, other models, tools/media or production changes.
A quota/auth failure, overrun or ambiguous started call stops all traffic. A known provider
503 may permit a distinct remaining diagnostic on the other surface, never replay.

Per project: one direct native generateContent probe with thinkingLevel low; one request
through the actual local router Responses route using Google compatible Chat Completions
with provider-default thinking. Only after compatible nonstream success, one router stream
with usage, completed text, settlement and cleanup verification. Native failure does not
assert compatible failure. Exact model gemini-3.8-flash, same simple bounded prompt. Existing
strict guards validate endpoint/auth/body; never retain secrets, prompts, outputs or state.

Preserve provider status/error enum, timeout phase, fixed safe structural envelope summary,
usage and public completion/settlement flags. Capture bounded errors using an allowlist
(INVALID_ARGUMENT, UNAVAILABLE, RESOURCE_EXHAUSTED, PERMISSION_DENIED, NOT_FOUND,
UNAUTHENTICATED, INTERNAL); unknown statuses become other, no raw messages. Timeout/unknown
records stay consumed and stop. Hold original shared stage lock plus new whole-run lock.
Before any awaited dispatch persist attempt ownership; enforce no replay on existing ledger.

Initially retain existing verifier timing; if direct evidence identifies the short verifier
timeout as limiting, propose a separate bounded timing amendment. Verifier model selection
becomes parameterized with original 3.5 defaults preserved. Real runtime remains unchanged
unless a concrete evidenced defect is independently reviewed. Focused/full checks and
contextual independent runner review before dispatch. Subsequent rollout requires exact
five-project production configuration and separate evidence; this diagnostic alone does
not authorize production cut-over or claim deployed 3.8 availability.

- [Inputs](inputs.md)
- [Activities](activities.md)
- [Outputs](outputs.md)
- [Exit criteria](exit-criteria.md)
- [Risks](risk-register.md)
- [Evidence](evidence.md)
