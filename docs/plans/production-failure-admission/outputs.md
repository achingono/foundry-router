# Outputs

## Mandatory Outputs

| Output | Description | Format |
|---|---|---|
| Admission matrix | Per-probe status/type, no-egress evidence (counter deltas + zero reservations), without bodies or secrets | Markdown table in `evidence.md` |
| Inference settlement | `fs-swarm` non-stream/stream HTTP/completion/usage/event counts, local estimated debits, cleanup state | Markdown table in `evidence.md` |
| Failure-state snapshot | Before/after readiness, backend health/cooldown, canonical credit groups, reconciliation staleness, metrics presence | Markdown table in `evidence.md` |
| Remaining gates | Explicit `fs-openclaw`, live upstream 429/5xx failover (still unverified by design), Table cut-over, embeddings, authoritative cost reconciliation status | Markdown list in `evidence.md` |

## Optional Outputs

- Redacted diagnostics excerpt (model catalog, health states) where it aids review; never keys, prompts, outputs, or error bodies.

## Output Quality Checklist

- [ ] All mandatory outputs produced
- [ ] All outputs reviewed before gate
- [ ] Evidence log updated with output references
- [ ] Status vocabulary (`Implemented`, `Partially implemented`, `Planned`, `Design target`) used consistently; no unverified behavior described as deployed
- [ ] All costs labeled local estimates, not Azure billed amounts
- [ ] Relative links resolve; final diff contains no secrets or present-tense overclaims
