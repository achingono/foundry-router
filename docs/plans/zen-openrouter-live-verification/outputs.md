# Live verification outputs

| Output | Description | Format |
| --- | --- | --- |
| Numeric live evidence | Per-case upstream/public status and usage, prices, balance deltas, cleanup checks and halt records | Markdown (`evidence.md`) |
| Review records | [Independent plan review](review.md), harness implementation review and contextual evidence review | Markdown |
| Verification tooling | Isolated harness, fixed manifest, durable ledger and bounded redacted observer | Source and offline tests |
| Local execution records | Five fixed IDs, durable dispatch intents and schema-validated sanitized results; ignored, no raw bodies/secrets | Local-only state |
| Defect amendments (only if evidence establishes one) | Separately reviewed plan deltas, never inline code fixes | Markdown |
