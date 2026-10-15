**Approved at plan level; no blockers found** in [anthropic-nullable-amendment.md](/Users/achingono/source/repos/foundry-router/docs/plans/opencode-zen-five-models/anthropic-nullable-amendment.md).

- The captured public SDK schemas support absent/null `container`, `diagnostics`, and `stop_details`, plus absent/null/empty-list text `citations`. Require explicit type/value checks; reject other values, unknown fields, and unsupported content. Drop accepted metadata.
- Preserve cache-inclusive usage extraction before conversion, including settlement on rejected output. Request, authentication, header, and streaming constraints remain unchanged.
- Explicit offset-hour/minute bounds address the reviewed timestamp normalization issue; regression coverage should include all three envelope paths.
- Economics reconcile: `$0.09 − $0.000453 − $0.000252 − $0.000112 = $0.089183`. Seeding `$0.088` discards `$0.001183`; production remains `$9.90`, with unchanged reserves and no replenishment or transfer.
- The new fixed identity must contain exactly fourteen cases, seven per environment. Preserve all four historical manifests/ledgers and the diagnostic; validate the latest two-pass/third-failure prefix, cleared reservations, stopped writer, and exact accounting.

Full verification and independent code/packet review remain gates before fresh staging calls. The metadata explanation remains a hypothesis until live acceptance.

Reported runtime facts were treated as supplied evidence. No edits, inference, private credential-data reads, or subagents were used.