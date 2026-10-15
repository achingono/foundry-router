**Approved for implementation. No plan blockers.**

- Accepting only documented, validated `modelStatus` metadata is a narrow adapter correction. Shared validation must cover nonstream responses and every stream envelope, including usage-only events. Arbitrary unknown fields must continue to fail closed.
- Credit accounting is consistent: **0.100000 − 0.000018 − 0.004000 = 0.095982 USD** staging; **9.90 USD** production remains unchanged. The diagnostic debit is irrevocable, with no replenishment or staging-to-production transfer.
- The replacement identity and seed must be fixed and independently bound to the original failed ledger, consumed diagnostic and stopped snapshot. Preserve the original runner’s failure/replay rejection; validate historical failure evidence through a separate path.
- Eighteen fresh calls remain bounded to nine staging and nine production, behind verification, new-image review and the inherited stopped-writer/all-account handoff gates. Halt on any failed or ambiguous slot.

`modelStatus` remains a plausible cause, not a confirmed diagnosis. This approves the plan only; implementation and the concrete execution packet still require review.

Read-only review completed without edits, inference, private-packet reads or subagents.