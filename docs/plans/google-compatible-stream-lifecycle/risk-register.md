# Stream lifecycle Risks

| Risk | Mitigation |
| --- | --- |
| Test buffers hide cancellation/early delivery | Real loopback socket and immediate forwarding observer |
| Partial usage lost on disconnect | Persist conservative observed maxima before next await; retain full reservation |
| Failed cancellation mistaken for provider exact cost | Separate conservative settlement from observed terminal usage |
| Token/request overrun | Existing nonrefundable ledger caps and global overrun halt |
| Prompts/output/signatures exposed | Fixed prompts in verifier code, usage/timing/flags only in evidence |
| Nonzero thinking absent | Leave unknown; never infer from task difficulty |
