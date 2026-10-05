# Real Foundry inference smoke verification

## Status: Implemented

Send one non-streaming and one streaming Responses request per configured real model using the isolated memory test app. Synthetic pricing/credit estimates remain test-only. Provider failure/cooldown tests, embeddings and production cut-over remain separate gates.

Both models passed non-streaming and streaming after correcting Azure Responses v1 routing and terminal usage settlement. Local estimated debit matched usage; no active reservations remained. No prompts, outputs or credential values are recorded.

- [Inputs](inputs.md)
- [Activities](activities.md)
- [Outputs](outputs.md)
- [Exit criteria](exit-criteria.md)
- [Risks](risk-register.md)
- [Evidence](evidence.md)
